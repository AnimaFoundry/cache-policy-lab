"""Verify the explicit reviewed text-file manifest; never crawl arbitrary files."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracked", action="store_true", help="Also require Git's tracked files to equal the review allowlist")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest_path = "docs/provenance.json"
    manifest = json.loads((root / manifest_path).read_text(encoding="utf-8"))
    records = manifest["working_tree_snapshot"]["files"]
    names = {row["path"] for row in records}
    if len(names) != len(records):
        raise SystemExit("Duplicate manifest path")
    for row in records:
        name = row["path"]
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
            raise SystemExit("Invalid manifest path")
        target = root / relative
        if any(part.is_symlink() for part in (target, *target.parents)):
            raise SystemExit("Symlink in manifest path: " + name)
        data = target.read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise SystemExit("Reviewed source hash mismatch: " + name)
        if b"\r" in data:
            raise SystemExit("Non-LF source line endings: " + name)
    if args.tracked:
        tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode("utf-8").split("\0")
        actual = {name for name in tracked if name}
        expected = names | {manifest_path}
        if actual != expected:
            raise SystemExit("Tracked files differ from review allowlist: " + str(sorted(actual ^ expected)))
    print("Verified", len(records), "reviewed source hashes; provenance record is Git-versioned separately")


if __name__ == "__main__":
    main()
