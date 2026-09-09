"""Generate only two original synthetic package fixtures, from this fixed recipe."""
from pathlib import Path
import argparse
import json
import tempfile


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    hot = [f"hot-{i}" for _ in range(2) for i in range(3)]
    for phase in range(2):
        hot += [f"scan-{phase}-{i}" for i in range(16)]
        hot += [f"hot-{i}" for _ in range(6) for i in range(3)]
    adverse = [f"pair-{i}" for i in range(12) for _ in range(2)]
    for name, keys, description in (
        ("hot_scan", hot, "Original fixed synthetic hot-prefix and one-touch scan example"),
        ("two_touch", adverse, "Original adverse example: each prefix used exactly twice, then never again"),
    ):
        records = [dict(type="trace_metadata", schema_version=1, trace_id=name,
                        data_classification="SYNTHETIC", description=description)]
        records += [dict(type="request", key=key, prefix_tokens=64, suffix_tokens=16) for key in keys]
        (destination / (name + ".jsonl")).write_text(
            "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in records) + "\n", encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare the fixed recipe with committed fixture bytes without changing them")
    args = parser.parse_args()
    destination = Path(__file__).resolve().parents[1] / "src/cache_policy_lab/examples"
    if args.check:
        with tempfile.TemporaryDirectory() as temp:
            generated = Path(temp)
            generate(generated)
            for name in ("hot_scan.jsonl", "two_touch.jsonl"):
                if (generated / name).read_bytes() != (destination / name).read_bytes():
                    raise SystemExit("Synthetic fixture recipe mismatch: " + name)
        print("Both synthetic fixtures match the fixed recipe byte-for-byte")
    else:
        generate(destination)


if __name__ == "__main__":
    main()
