"""Strict, declared-public JSONL trace intake. Original inputs are never rewritten."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .kernel import Request


class TraceError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def content_hash(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def local_path(root, relative):
    """Scope file access to an explicitly selected directory, excluding local secrets."""
    original_base = Path(root).absolute()
    raw = str(relative)
    parts = raw.replace("\\", "/").split("/")
    protected = {".auth", ".git", ".codex", ".agents", "input", "output", "exports", "quarantine", "raw", "media"}
    for parent in (original_base, *original_base.parents):
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise TraceError("Linked roots are not allowed")
    base = original_base.resolve()
    if any(part.lower().rstrip(". ") in protected or part.lower().startswith(".chrome") for part in (*original_base.parts, *base.parts)):
        raise TraceError("Selected root lies within a protected data/credential directory")
    if (Path(raw).is_absolute() or ":" in raw or not raw
            or any(part in {"", ".", ".."} or part.endswith((".", " ")) for part in parts)
            or any(part.lower() in protected or part.lower().startswith(".chrome") for part in parts)
            or any(re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part) for part in parts)):
        raise TraceError("Use a relative path outside protected data and credential directories")
    cursor = base
    for part in parts:
        cursor = cursor / part
        if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
            raise TraceError("Linked input/output paths are not allowed")
    resolved = cursor.resolve()
    if not resolved.is_relative_to(base):
        raise TraceError("Path escapes the selected root")
    return resolved


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TraceError("Duplicate JSON field: " + key)
        result[key] = value
    return result


def _reject_constant(value):
    raise TraceError("Non-finite JSON constant: " + value)


@dataclass(frozen=True)
class Trace:
    metadata: dict
    requests: tuple[Request, ...]
    raw_sha256: str
    normalized_sha256: str


def parse_trace(raw: bytes, *, max_requests=100_000, max_bytes=32_000_000):
    if not isinstance(raw, bytes) or len(raw) > max_bytes:
        raise TraceError("Trace must be bytes within the configured input size limit")
    if isinstance(max_requests, bool) or not isinstance(max_requests, int) or max_requests <= 0:
        raise TraceError("max_requests must be a positive integer")
    try:
        lines = raw.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise TraceError("Trace must be UTF-8 JSONL") from exc
    if not lines:
        raise TraceError("Trace metadata is missing")
    records = []
    for number, line in enumerate(lines, 1):
        if not line.strip() or len(line) > 65_536:
            raise TraceError(f"Line {number}: blank or oversized JSONL record")
        if number > max_requests + 1:
            raise TraceError("Trace exceeds the request limit")
        try:
            record = json.loads(line, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        except (ValueError, RecursionError) as exc:
            raise TraceError(f"Line {number}: invalid JSON record ({exc})") from None
        if not isinstance(record, dict):
            raise TraceError(f"Line {number}: expected a JSON object")
        records.append(record)
    metadata = records[0]
    required = {"type", "schema_version", "trace_id", "data_classification", "description"}
    if set(metadata) - (required | {"sanitization_note"}) or not required <= metadata.keys():
        raise TraceError("Metadata fields do not match the trace schema")
    if metadata["type"] != "trace_metadata" or type(metadata["schema_version"]) is not int or metadata["schema_version"] != 1:
        raise TraceError("Unsupported trace metadata version/type")
    if not isinstance(metadata["trace_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", metadata["trace_id"]):
        raise TraceError("trace_id must be a short opaque identifier")
    if type(metadata["data_classification"]) is not str or metadata["data_classification"] not in {"SYNTHETIC", "SANITIZED"}:
        raise TraceError("Only declared SYNTHETIC or explicitly SANITIZED traces are accepted")
    if not isinstance(metadata["description"], str) or not metadata["description"].strip():
        raise TraceError("Trace description is required")
    note = metadata.get("sanitization_note")
    if "sanitization_note" in metadata and (not isinstance(note, str) or not note.strip()):
        raise TraceError("sanitization_note must be nonempty descriptive text")
    if metadata["data_classification"] == "SANITIZED" and (not isinstance(note, str) or not note.strip()):
        raise TraceError("SANITIZED data requires an explicit sanitization_note")
    requests, sizes = [], {}
    for number, record in enumerate(records[1:], 2):
        if set(record) != {"type", "key", "prefix_tokens", "suffix_tokens"} or record["type"] != "request":
            raise TraceError(f"Line {number}: unexpected request fields; raw prompts/URLs are not accepted")
        try:
            request = Request(record["key"], record["prefix_tokens"], record["suffix_tokens"])
        except (ValueError, TypeError) as exc:
            raise TraceError(f"Line {number}: invalid request ({exc})") from None
        if request.key in sizes and sizes[request.key] != request.prefix_tokens:
            raise TraceError(f"Line {number}: one key cannot denote different prefix sizes")
        sizes[request.key] = request.prefix_tokens
        requests.append(request)
    if not requests:
        raise TraceError("At least one request is required")
    return Trace(dict(metadata), tuple(requests), hashlib.sha256(raw).hexdigest(), content_hash(records))


def read_trace(path, *, max_bytes=32_000_000):
    # Bound the read itself, not only parsing after an unbounded allocation.
    with Path(path).open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    return parse_trace(raw, max_bytes=max_bytes)


def verify_trace(trace):
    records = [trace.metadata] + [dict(type="request", key=r.key, prefix_tokens=r.prefix_tokens, suffix_tokens=r.suffix_tokens)
                                  for r in trace.requests]
    if content_hash(records) != trace.normalized_sha256:
        raise TraceError("Trace metadata or events changed after input hashing")
