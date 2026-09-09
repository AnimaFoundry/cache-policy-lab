from __future__ import annotations

import argparse
import json
import sys
from importlib.resources import files

from . import __version__
from .report import compare, markdown
from .trace import local_path, parse_trace, read_trace


def parser():
    root = argparse.ArgumentParser(prog="cache-policy-lab", description="Auditable L2 cache-policy comparisons on declared synthetic/sanitized traces")
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument("--root", default=".", help="Directory containing permitted relative input/output paths")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("compare", "demo"):
        cmd = commands.add_parser(name)
        if name == "compare":
            cmd.add_argument("trace", nargs="+", help="Relative JSONL trace files")
        cmd.add_argument("--out", required=True, help="New relative output directory; never overwritten")
        cmd.add_argument("--policies", nargs="+", default=["lru", "two_hit", "fifo"])
        cmd.add_argument("--baseline", default="lru")
        cmd.add_argument("--capacity-tokens", type=int, default=768)
        cmd.add_argument("--history-slots", type=int, default=64)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        dest = local_path(args.root, args.out)
        if dest.exists():
            raise ValueError("Output directory exists; choose a fresh run directory")
        if args.command == "demo":
            traces = [parse_trace(files("cache_policy_lab").joinpath("examples", name).read_bytes())
                      for name in ("hot_scan.jsonl", "two_touch.jsonl")]
        else:
            traces = [read_trace(local_path(args.root, relative)) for relative in args.trace]
        result = compare(traces, policies=args.policies, baseline=args.baseline,
                         capacity_tokens=args.capacity_tokens, history_slots=args.history_slots)
        dest.mkdir(parents=True)
        (dest / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        (dest / "REPORT.md").write_text(markdown(result), encoding="utf-8")
        print(json.dumps(dict(status="COMPLETE_L2_COMPARISON", version=__version__,
            trace_count=len(traces), run_count=len(result["runs"]), deterministic_sha256=result["deterministic_sha256"]), indent=2))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print("cache-policy-lab: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
