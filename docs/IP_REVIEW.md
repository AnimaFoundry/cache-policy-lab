# Cache Policy Lab: scoped publication and provenance review

Review date: **2026-09-09**, Asia/Shanghai. Reviewer: Codex research agent.
Review state: **`scoped_open_source_review`**. Artifact type: **`research_tool`**.
This is a technical publication review, not a lawyer's opinion or a freedom-to-operate (FTO) clearance. Patent legal status and global FTO remain **UNKNOWN**.

## Decision and exact boundary

Continue toward the first software release, subject to the artifact checks below. The reviewed implementation in `src/cache_policy_lab` is a Python standard-library-only, offline cache experiment: read synthetic or explicitly sanitized JSONL events with opaque prefix IDs and token counts, apply ordinary LRU, FIFO or bounded-history two-hit admission, enforce declared modeled budgets, and produce deterministic comparison reports. Misses charge prefix work; all requests charge uncached suffix work. No actual tokenization or inference runs. No concrete claim-overlap blocker was identified in the four previously flagged patent leads for this design. This finding is limited to those leads and the stated design.

This is not a new cache invention claim. It does not implement LLM inference, split prompts into prefill chunks, batch prefill with decode, dispatch inference nodes, manipulate GPU KV blocks, implement OIE-011 shared-memory reclamation, or implement OIE-012 drift-triggered resets. Adding those mechanisms changes the review scope. Merely calling a program an experiment or making it open source does not establish a patent exemption.

Earlier internal invention-screening restrictions remain applicable to invention candidates outside this standalone repository. This separate software review does not establish invention validity or novelty. Normal software publication can proceed after its own code, provenance, licensing and execution checks; this record does not require a specialist sign-off for every routine tool. A specific close claim, disputed contribution or notice of alleged infringement requires assessment of that concrete issue before distributing the affected feature.

## Copyright, license and development provenance

The current implementation was written for this task with AI assistance from the local requirements and elementary cache semantics. The parent implementation agent confirmed no third-party implementation was consulted or copied this turn; the official Apache license was copied from the existing local license file. The new kernel was compared with the existing local experiment for behavior. The original synthetic recipe is in `scripts/make_cache_lab_fixtures.py`. No third-party implementation was downloaded or copied for this review. The attached provenance record distinguishes this development history from a legal guarantee of originality, ownership or non-infringement.

The reviewer read the kernel, trace intake, report generation, CLI, packaging, README, NOTICE and synthetic-generation recipe. Runtime imports use the standard library or this package; `pyproject.toml` declares no runtime dependencies and pins `setuptools==84.0.0` for building. The license bytes match the prior local official Apache text. The 0.1.0 candidate changes package version and release documentation; its kernel, parser, report and CLI behavior remain within this reviewed scope. The JSON record contains candidate **working-tree snapshot** hashes and excludes its own file to avoid self-reference. The external release receipt must bind the full 24-file tree, including that record, to the exact tested commit; the candidate record itself is not a publication receipt.

The U.S. Copyright Office distinguishes program expression from functional aspects such as algorithms. That distinction supports writing our own implementation of known behavior; it does not authorize copying somebody else's source, explanatory prose, tests, figures or datasets. This U.S. guidance is not a global copyright assessment. [Copyright Office, Circular 61, page 1](https://www.copyright.gov/circs/circ61.pdf)

Use **Apache-2.0** for the original software, include its complete license text, and retain any applicable attribution or modification notices. Its contributor patent grant covers only qualifying claims licensable by contributors; it is not a license to unrelated third-party patents. Its trademark and warranty provisions also do not supply clearance. Do not suggest endorsement by Apache, paper authors or competing projects. [Apache Software Foundation, Apache License 2.0, sections 2–4, 6–7](https://www.apache.org/licenses/LICENSE-2.0)

The two-hit baseline has established intellectual antecedents. Johnson and Shasha's **2Q (1994)** discusses admission based on repeated references and uses distinct queues. Cite it as related work; the simple bounded-history baseline here is not asserted to reproduce full 2Q or to be novel. No paper code, trace, figure or benchmark result is bundled. [2Q, section 2, pages 440–442](https://www.vldb.org/conf/1994/P439.PDF)

## Previously flagged patent leads against this design

The following compares published claim language with the proposed executable behavior. Patent documents were read through Google Patents as a document mirror, not an official legal-status register. English translations are used for the Chinese B documents; the Chinese A document was read in Chinese. This is a feature screen, without legal claim construction, equivalents analysis or complete family search. Patent rights and infringement analysis are distinct from patentability: the USPTO describes infringement assessment as comparing claims with the product or process. [USPTO, Managing a patent](https://www.uspto.gov/patents/basics/manage)

| Lead and reviewed claims | Material mechanism in the reviewed text | Scope comparison and action |
| --- | --- | --- |
| [US20250238694A1](https://patents.google.com/patent/US20250238694A1/en), published 2025-07-24; claims 1–20 | LLM prompt division and hybrid batches containing prefill and decode work; dependent claims add sizing and device details. | Object-event replay has no prompt division, inference batch or inference execution. Keep production prefill/decode scheduling out of this release. Displayed status: Pending; verified status: UNKNOWN. |
| [CN120950665A](https://patents.google.com/patent/CN120950665A/zh), published 2025-11-14; claims 1–10 | Inference-node selection using shared-prefix-cache and local-generation-cache hit information. | A local modeled object cache has no shared/local inference architecture or node dispatch. Do not turn the CLI into this routing mechanism without a new review. Displayed status: Pending; verified status: UNKNOWN. |
| [CN121050863B](https://patents.google.com/patent/CN121050863B/en), published 2026-02-17; claims 1–4 and 10–13 | Priority/resource-limited prefill queue construction with an adder, LoRA limits and model inference; dependent claim 4 adds GPU-occupancy adjustment. | Cache budget accounting is not the described prefill queue construction. There are no tokenized inference requests, LoRA limits or GPU controller. Displayed status: Active; verified status: UNKNOWN. |
| [CN120909737B](https://patents.google.com/patent/CN120909737B/en), published 2025-12-09; claim 1 and claims 2–7 inspected | Separate prefill/decode servers, feedback queues and deep-reinforcement-learning routing; granted claim 1 also specifies shared-prefix matching and execution-time prediction. | Replay has no server selection, trained scheduler, prompt-prefix search or inference execution. The granted text extends the earlier A-only review; it does not establish clearance. Displayed status: Active; verified status: UNKNOWN. |

These differences support the limited engineering decision to continue packaging. They are not a finding that every possible cache-simulation or admission claim has been searched, or that a published application cannot affect a later release. Before adding a close implementation, determine relevant jurisdictions, current granted claims, families and legal status; use qualified patent advice when the concrete overlap requires legal interpretation.

## Name check

On 2026-09-09 the connected GitHub repository-search tool returned an empty repository list for **`"cache-policy-lab" in:name`**. A site-restricted indexed search also returned no results. The [GitHub search page](https://github.com/search?q=%22cache-policy-lab%22&type=repositories) could not be retrieved through the web tool. This is an obvious repository-name collision check, not exhaustive availability or trademark clearance. Confirm the exact `AnimaFoundry/cache-policy-lab` destination before creation and identify the publisher as AnimaFoundry. No logos or third-party branding are included in the reviewed design.

## Before the public release

1. Inspect the final allowlisted package files; record their hashes and the exact commit in the release manifest. Confirm the implementation still matches this scope and the provenance declaration.
2. Confirm no vendored implementation, third-party assets or unreviewed dependencies were introduced. Python is a runtime prerequisite; do not bundle a Python interpreter. Record build dependencies separately from runtime dependencies.
3. Include the software license, source attribution, precise simulation limitations and a route for reporting rights concerns. Do not claim novelty, patent clearance or real-world performance from toy traces.
4. Package only authored synthetic fixtures. User-supplied trace processing grants no right to redistribute that trace; never upload it as part of a release by default.
5. Pass the actual package/CLI tests and clean Linux CI for the release revision. These checks validate behavior and packaging; they do not prove legal clearance.

The linked `provenance.json` is the machine-readable review record. No source-code similarity audit across all public/private code, native patent-register search, complete general cache-patent search, jurisdiction-specific FTO opinion, trademark-register search or human legal review has been completed. Publishing this scoped tool still carries operational IP risk; it cannot promise zero disputes.

## Reporting a concrete rights concern

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the reporting route and handling
policy. Identify the affected file/version and the specific claimed work or patent
without posting private documents or personal data.
