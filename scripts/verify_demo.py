"""Run the installed CLI twice and check the reviewed deterministic model result."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    expected = json.loads((root / "docs/reproducibility.json").read_text(encoding="utf-8"))
    cli = Path(sys.executable).parent / ("cache-policy-lab.exe" if sys.platform == "win32" else "cache-policy-lab")
    reports = []
    with tempfile.TemporaryDirectory() as temp:
        for name in ("first", "repeat"):
            subprocess.run([str(cli), "--root", temp, "demo", "--out", "reports/" + name], check=True, cwd=temp)
            report = json.loads((Path(temp) / "reports" / name / "report.json").read_text(encoding="utf-8"))
            deterministic = {key: value for key, value in report.items() if key not in ("deterministic_sha256", "host_environment")}
            digest = hashlib.sha256(json.dumps(deterministic, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()
            if digest != report["deterministic_sha256"] or digest != expected["deterministic_sha256"]:
                raise SystemExit("Deterministic demo digest mismatch")
            measured = {row["trace_id"] + "/" + row["policy"]: row["metrics"]["total_work_tokens"] for row in report["runs"]}
            if measured != expected["total_work_tokens"]:
                raise SystemExit("Demo counters differ from hand-reviewed expected values")
            if not all(row["metrics"]["resource_budget_respected"] for row in report["runs"]):
                raise SystemExit("Modeled resource budget violated")
            reports.append(report)
    if reports[0] != reports[1]:
        raise SystemExit("Same-environment demo repetition differs")
    print(json.dumps({"deterministic_sha256": reports[0]["deterministic_sha256"], "host_environment": reports[0]["host_environment"], "runs": len(reports[0]["runs"]), "separate_cli_processes": 2}, sort_keys=True))


if __name__ == "__main__":
    main()
