"""Synthetic-only parser/CLI integration and report regressions."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from cache_policy_lab.__main__ import main
from cache_policy_lab.report import compare
from cache_policy_lab.trace import TraceError, local_path, parse_trace


def fixture(requests=None, **changes):
    metadata = dict(type="trace_metadata", schema_version=1, trace_id="test", data_classification="SYNTHETIC", description="synthetic test")
    metadata.update(changes)
    records = [metadata] + (requests if requests is not None else [dict(type="request", key="a", prefix_tokens=64, suffix_tokens=16)] * 2)
    return ("\n".join(json.dumps(row) for row in records) + "\n").encode()


class TraceTests(unittest.TestCase):
    def test_raw_and_normalized_hashes_are_separate(self):
        raw = fixture()
        a = parse_trace(raw)
        b = parse_trace(raw.replace(b'": ', b'":'))
        self.assertNotEqual(a.raw_sha256, b.raw_sha256)
        self.assertEqual(a.normalized_sha256, b.normalized_sha256)
        self.assertEqual(len(a.requests), 2)

    def test_reject_unknown_fields_duplicates_and_nonfinite_json(self):
        for raw in (fixture().replace(b'"prefix_tokens": 64', b'"prefix_tokens": 64, "prefix_tokens": 2'),
                    fixture().replace(b'"prefix_tokens": 64', b'"prefix_tokens": NaN'),
                    fixture().replace(b'"key": "a"', b'"key": "a", "prompt": "not permitted"'),
                    fixture() + b'\n', fixture() + b'[]\n', b'\xff'):
            with self.subTest(raw=raw[:30]), self.assertRaises(TraceError):
                parse_trace(raw)

    def test_strict_numeric_identity_and_input_limits(self):
        base = dict(type="request", key="a", prefix_tokens=64, suffix_tokens=16)
        for request in ({**base, "prefix_tokens": True}, {**base, "prefix_tokens": 1.5},
                        {**base, "prefix_tokens": 0}, {**base, "suffix_tokens": -1}, {**base, "key": "https://example.invalid/x"}):
            with self.subTest(request=request), self.assertRaises(TraceError):
                parse_trace(fixture([request]))
        with self.assertRaises(TraceError):
            parse_trace(fixture([base, {**base, "prefix_tokens": 65}]))
        with self.assertRaises(TraceError):
            parse_trace(fixture(), max_requests=1)
        with self.assertRaises(TraceError):
            parse_trace(fixture(), max_bytes=1)

    def test_data_declaration_required_and_never_auto_sanitized(self):
        for changes in (dict(data_classification="RAW"), dict(data_classification="SANITIZED"), dict(schema_version=True),
                        dict(data_classification=[]), dict(sanitization_note={"unreviewed": True})):
            with self.subTest(changes=changes), self.assertRaises(TraceError):
                parse_trace(fixture(**changes))
        trace = parse_trace(fixture(data_classification="SANITIZED", sanitization_note="All fields are synthetic; explicit test fixture declaration"))
        self.assertEqual(trace.metadata["data_classification"], "SANITIZED")

    def test_protected_and_aliased_paths_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for value in ("../x", ".auth/x", ".auth./x", ".chrome-test/x", "input/x", "output/x", "a/../x", "NUL.txt", "a//b"):
                with self.subTest(value=value), self.assertRaises(TraceError):
                    local_path(temp, value)
            for name in (".auth", "input", ".chrome-test"):
                with self.subTest(root=name), self.assertRaises(TraceError):
                    local_path(Path(temp) / name, "trace.jsonl")


class ReportTests(unittest.TestCase):
    def test_metadata_mutation_cannot_reuse_the_old_input_hash(self):
        trace = parse_trace(fixture())
        trace.metadata["description"] = "changed after hashing"
        with self.assertRaises(TraceError):
            compare([trace])

    def test_all_policies_reported_deterministically_with_real_adverse_result(self):
        requests = [dict(type="request", key=f"a-{i}", prefix_tokens=64, suffix_tokens=16) for i in range(3) for _ in range(2)]
        trace = parse_trace(fixture(requests))
        result = compare([trace])
        self.assertEqual(result, compare([trace]))
        self.assertEqual(len(result["runs"]), 3)
        row = next(r for r in result["comparisons"] if r["policy"] == "two_hit")
        self.assertEqual(row["work_delta_tokens"], 192)
        self.assertEqual(row["outcome"], "MORE_MODEL_WORK")
        self.assertEqual(result["artifact_type"], "research_tool")

    def test_duplicate_trace_or_policy_and_absent_baseline_rejected(self):
        trace = parse_trace(fixture())
        with self.assertRaises(ValueError):
            compare([trace, trace])
        for policies in (("lru", "lru"), ("unknown",), ("two_hit",)):
            with self.assertRaises(ValueError):
                compare([trace], policies=policies)

    def test_cli_demo_and_failed_input_leave_originals_untouched(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root = Path(temp)
            self.assertEqual(main(["--root", temp, "demo", "--out", "reports/demo"]), 0)
            report = json.loads((root / "reports/demo/report.json").read_text(encoding="utf-8"))
            self.assertEqual(len(report["inputs"]), 2)
            self.assertEqual(len(report["runs"]), 6)
            before = (root / "reports/demo/report.json").read_bytes()
            self.assertEqual(main(["--root", temp, "demo", "--out", "reports/demo"]), 2)
            self.assertEqual(before, (root / "reports/demo/report.json").read_bytes())
            (root / "broken.jsonl").write_bytes(b"not-json")
            self.assertEqual(main(["--root", temp, "compare", "broken.jsonl", "--out", "reports/failed"]), 2)
            self.assertFalse((root / "reports/failed").exists())


if __name__ == "__main__":
    unittest.main()
