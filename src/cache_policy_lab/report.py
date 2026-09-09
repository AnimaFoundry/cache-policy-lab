"""Complete, deterministic model reports; no invented wins or novelty conclusions."""
from __future__ import annotations

import platform
import sys

from . import __version__
from .kernel import FIFO, LRU, TwoHit, simulate
from .trace import content_hash, verify_trace

POLICIES = {"lru": LRU, "two_hit": TwoHit, "fifo": FIFO}


def compare(traces, *, policies=("lru", "two_hit", "fifo"), baseline="lru", capacity_tokens=768, history_slots=64):
    traces = list(traces)
    policies = tuple(policies)
    if not traces or len({trace.metadata["trace_id"] for trace in traces}) != len(traces):
        raise ValueError("Provide traces with unique trace_id values")
    if not policies or len(set(policies)) != len(policies) or set(policies) - POLICIES.keys() or baseline not in policies:
        raise ValueError("Select unique known policies and include the comparison baseline")
    runs, comparisons, inputs = [], [], []
    for trace in traces:
        verify_trace(trace)
        tid = trace.metadata["trace_id"]
        inputs.append(dict(metadata=dict(trace.metadata), raw_sha256=trace.raw_sha256,
                           normalized_sha256=trace.normalized_sha256, requests=len(trace.requests)))
        metrics = {}
        for name in policies:
            metrics[name] = simulate(iter(trace.requests), POLICIES[name](), capacity_tokens=capacity_tokens, history_slots=history_slots)
            runs.append(dict(trace_id=tid, policy=name, metrics=metrics[name]))
        baseline_work = metrics[baseline]["total_work_tokens"]
        for name in policies:
            work = metrics[name]["total_work_tokens"]
            delta = work - baseline_work
            comparisons.append(dict(trace_id=tid, policy=name, baseline=baseline, work_delta_tokens=delta,
                work_reduction_fraction=(baseline_work - work) / baseline_work if baseline_work else None,
                outcome="LESS_MODEL_WORK" if delta < 0 else "MORE_MODEL_WORK" if delta > 0 else "EQUAL_MODEL_WORK"))
    payload = dict(schema_version=1, tool="Cache Policy Lab", version=__version__, artifact_type="research_tool",
        validation_level="L2", protocol="cache-policy-lab-v1", inputs=inputs, runs=runs, comparisons=comparisons,
        budget=dict(capacity_tokens=capacity_tokens, history_slots=history_slots), baseline=baseline,
        limitations=["Offline abstract token-work model, not GPU latency, throughput, quality or production validation.",
            "Metadata classification is the submitting operator's declaration, not automatic proof of sanitization.",
            "Cache-token and recent-history budgets are modeled; Python heap and controller CPU cost are not benchmarked.",
            "Policy callbacks receive current/past state only; arbitrary in-process Python plugins are trusted, not sandboxed.",
            "All supplied traces and policies are reported; conclusions apply only to this input suite.",
            "This is an engineering research tool; no new-invention, patentability or freedom-to-operate finding is asserted."],
        references=[dict(title="TinyLFU: A Highly Efficient Cache Admission Policy", url="https://arxiv.org/abs/1512.00727",
                         note="Related frequency-admission prior work; the simple two-hit example is not an implementation of TinyLFU."),
                    dict(title="libCacheSim", url="https://github.com/1a1a11a/libCacheSim",
                         note="Existing cache simulation software; its implementation is not a dependency or copied source.")])
    return {**payload, "deterministic_sha256": content_hash(payload),
            "host_environment": dict(python=sys.version.split()[0], platform=platform.system())}


def markdown(report):
    lines = ["# Cache Policy Lab comparison", "", "L2 offline model; work values below are modeled token-work units.", "",
        "| Trace | Policy | Baseline | Work difference | Work reduction |",
        "|---|---|---|---:|---:|"]
    for row in report["comparisons"]:
        reduction = row["work_reduction_fraction"]
        percent = "n/a" if reduction is None else f"{100 * reduction:.2f}%"
        lines.append(f"| {row['trace_id']} | {row['policy']} | {row['baseline']} | {row['work_delta_tokens']} | {percent} |")
    lines.extend(["", "Positive reduction means less modeled work; negative values are regressions.", "",
        "Deterministic report SHA-256: `" + report["deterministic_sha256"] + "`", "", "## Scope and limitations", ""])
    lines.extend("- " + value for value in report["limitations"])
    lines.extend(["", "Full counters, budgets and input hashes are in report.json.", ""])
    return "\n".join(lines)
