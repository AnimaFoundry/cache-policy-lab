# Cache Policy Lab

Compare elementary cache policies on declared synthetic or explicitly sanitized
request streams, with centrally counted work and resource invariants.
Version: **0.1.0**. This is research tooling;
no new-invention, production LLM benchmark or freedom-to-operate claim is made.

Source repository: [AnimaFoundry/cache-policy-lab](https://github.com/AnimaFoundry/cache-policy-lab).

The runtime uses Python 3.11+ and the standard library only. The package includes
LRU, simple two-hit admission, and FIFO examples. It does not run a model, manage
GPU memory, schedule live prefill/decode batches, or import production prompts.

## Install and try

From this repository root:

```console
python -m pip install .
cache-policy-lab demo --out reports/cache-lab-demo
cache-policy-lab compare trace.jsonl --out reports/cache-lab-comparison
```

Choose a new output directory for each run. Both `report.json` and `REPORT.md`
are written only after the complete comparison succeeds. The JSON preserves all
policies/traces, counters, budgets, regressions and input hashes. A separate
host-independent digest covers the deterministic result; Python/platform details
are outside that digest. The original input bytes are not rewritten or copied
into the report. Nothing is uploaded.

For an offline build in an environment already containing setuptools 84.0.0, use
`python -m pip install --no-build-isolation --no-deps .`. These instructions install
the source checkout; they do not imply availability from a package registry.

## JSONL input

The first line declares the trace; subsequent lines contain only requests:

```jsonl
{"type":"trace_metadata","schema_version":1,"trace_id":"example","data_classification":"SYNTHETIC","description":"Original synthetic example"}
{"type":"request","key":"prefix-a","prefix_tokens":64,"suffix_tokens":16}
{"type":"request","key":"prefix-a","prefix_tokens":64,"suffix_tokens":16}
```

Keys must be opaque identifiers. Dedicated prompt, URL or cookie fields and other
extra request fields are rejected; key syntax excludes ordinary web URLs. This
schema check cannot establish that an identifier or metadata text is free of
sensitive content. Descriptions and sanitization notes are copied into report.json;
provide only metadata safe to share. Positive prefix token sizes and nonnegative
suffix sizes must be integers, excluding booleans. A key always has the same
prefix size. Duplicate JSON fields, blank rows, non-finite numbers, malformed
UTF-8 and oversized traces fail closed. Default input limit is 32 MB / 100,000
requests. `SANITIZED` traces additionally require a `sanitization_note`; this is
an operator declaration and is not evidence that software has anonymized data.

CLI paths are relative to `--root` (default current directory). Protected local
collection/credential directories, traversal, symlinks and Windows path aliases
are rejected. Prepare permitted input separately; this tool does not crawl files.

## Policy interface and accounting

The engine calls `policy.decide(request, view)` once for each current request.
`Request`, `View` and `Decision` are immutable. `View` exposes current cache
state and the bounded previous request history, not a future-trace argument.
Policies request admission/eviction; the engine validates those decisions and
derives hits, misses and recomputation centrally. It rejects nonexistent or
duplicate eviction IDs and decisions exceeding the configured model budget.

Cache state is charged in abstract prefix tokens. History is charged in request
slots. Fixed prefix identity validation uses a separate harness registry of seen
keys, reported explicitly. This is not full Python heap or CPU accounting.
Custom in-process Python policies are trusted code; the callback interface does
not sandbox malicious code, meter hidden allocations, or prove absence of all
future-information leakage.

On a cache hit the model charges only the suffix. On a miss it charges prefix
plus suffix. Identical capacities and history limits apply to every policy.
Reports are L2 model evidence and do not predict wall-clock GPU speed. The built-in
suite contains a motivating hot+scan example and an adverse two-touch example;
do not report only the favorable row.

## Provenance and intellectual property

Source code is newly written for this project, with an independently implemented
event protocol. Related work includes [TinyLFU](https://arxiv.org/abs/1512.00727)
and [libCacheSim](https://github.com/1a1a11a/libCacheSim). Repeat-reference admission
also has antecedents in [2Q (1994)](https://www.vldb.org/conf/1994/P439.PDF).
Our simple two-hit example is not a complete 2Q implementation. Their source code is not
vendored or a package dependency. Our simple two-hit example is not TinyLFU.
The earlier development simulation is outside this standalone distribution.

The software is under Apache-2.0; full terms are in LICENSE. NOTICE retains the
origin and relevant attribution. An open-source license is not a determination
of third-party patent rights. The scoped prepublication review and unresolved
items are in [the scoped IP review](docs/IP_REVIEW.md) and
[provenance record](docs/provenance.json).
Do not claim legal clearance, a novel caching algorithm, or production validity.

## Release verification

The 0.1.0 source is prepared as a release candidate. Public release requires a
successful clean Linux acceptance run on the exact candidate commit, independent
reproduction, the scoped IP review and the reviewed file allowlist. The GitHub
release receipt, when available, identifies the published tag, commit and
acceptance evidence. A version string alone does not establish publication or a
package-registry upload. See `docs/reproducibility.json` for the reviewed expected
result and the checks actually observed when this source was prepared.

## Reproduce and contribute

Run `python -I -m unittest discover -s tests -v`,
`python scripts/make_cache_lab_fixtures.py --check`, and
`python scripts/verify_demo.py` after installation. The demo verification uses
the installed console command in two separate processes and checks every policy
against the reviewed counters and digest in `docs/reproducibility.json`. Source
bytes use LF line endings on every platform so raw fixture hashes remain stable.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and rights-concern
reporting instructions, and [CITATION.cff](CITATION.cff) for software citation.
