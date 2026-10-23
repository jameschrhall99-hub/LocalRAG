# Local RAG Engineering Project Plan

Prepared: 23 October 2026. Target machine: Windows 11, Radeon RX 9070 XT, 16 GB system RAM, Ryzen 7 5800X3D.

## 1. Project and outcome

Build **EvidenceOps**, a local assistant for the documentation and operation of a small FastAPI service. It answers documentation questions with inspectable citations, declines questions that its authorised sources cannot support, and runs a few tightly controlled, read-only diagnostics against a demonstration service.

The strongest portfolio feature will be its evaluation and failure analysis: another developer should be able to reproduce a baseline, introduce a regression, and see the quality gate fail with an explanation.

Aim for a complete, bounded engineering project over approximately **6–8 weeks / 60–100 focused hours**, allowing more time if Python, APIs, or testing are new. These are planning estimates. Start with 20 documents and 20 questions; expand after one vertical slice works.

Release deliverables:

- A CLI and FastAPI endpoint using the same application pipeline; a small evidence-viewing interface can follow.
- A pinned corpus of roughly 60–100 English FastAPI documentation pages plus 8–12 clearly labelled, self-authored service runbooks.
- Hybrid retrieval, structured answers, deterministic citation validation, conservative answer/abstain decisions, and controlled diagnostic tools.
- A reviewed evaluation dataset, deterministic automated tests, local semantic judging, and reports with enforced thresholds.
- A README with setup, measured results, an architecture diagram, threat model, limitations, and a short demonstration recording.

This is an applied AI engineering project. Training or fine-tuning a model is unnecessary for the first release.

## 2. Hardware and implementation choices

Your PC is sufficient for this scope. GPU memory and system RAM are separate budgets; the RX 9070 XT has 16 GB VRAM, while the stated 16 GB RAM must also accommodate Windows and development tools. Use the CPU for ingestion, small embeddings, retrieval, and tests; use the GPU for quantised language models.

| Component | Starting choice | Purpose |
|---|---|---|
| Language/environment | Python 3.12, virtual environment, locked dependencies | Reproducible Windows setup |
| Application | FastAPI, Pydantic, httpx, CLI | Typed contracts and one shared pipeline |
| Inference | Native Windows llama.cpp server | Local model inference with explicit resource controls |
| Answer model | Qwen3-4B GGUF, Q4_K_M | Small initial model; benchmark before upgrading |
| Evaluation judge | Qwen3-8B GGUF, Q4_K_M | Separate offline judging pass |
| Embeddings | BAAI/bge-small-en-v1.5 on CPU | Small English retrieval model |
| Metadata/lexical search | SQLite with FTS5/BM25 | Documents, access metadata, exact technical terms |
| Dense search | Normalised float32 vectors in NumPy | Exact cosine search over a small corpus |
| Fusion | Reciprocal rank fusion, stable tie-breaking | Combine lexical and dense candidates |
| Tests/reports | pytest, optional Hypothesis; JSONL, JSON, Markdown | Deterministic tests and auditable evaluations |
| Automation | GitHub-hosted deterministic tests; local full evaluation | Fit the available hardware |

These are deliberate starting choices, not claims that these models are the newest or best. The official [Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B-GGUF) and [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B-GGUF) repositories provide GGUF models under Apache 2.0. Pin an exact model revision and file hash.

The [BGE model card](https://huggingface.co/BAAI/bge-small-en-v1.5) specifies 384-dimensional embeddings and a 512-token sequence limit. Apply its documented retrieval instruction to queries, not passages. Start with 300–400 embedding-token chunks and 40-token overlap; count titles and headings within the limit and reject silent truncation.

For scale: 10,000 vectors × 384 dimensions × 4 bytes is about 15 MB, excluding metadata. Exact NumPy search is reasonable here. Add a vector database only if measured scale or access requirements justify it.

### Windows/AMD setup

Start with the current official [AMD llama.cpp Windows instructions](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/inference/llamacpp.html), selecting your GPU and Windows. Pin the working binary, runtime and driver versions in a hardware manifest. The older [AMD-validated Windows binaries guide](https://rocmdocs.amd.com/projects/radeon-ryzen/en/latest/docs/advanced/advancedrad/windows/llm/llamacpp.html) is another documented route. Match the runtime to the binary rather than combining arbitrary DLL versions.

If that setup proves troublesome, use an official llama.cpp Windows Vulkan build or the upstream [Vulkan build instructions](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md#vulkan). First prove a short model request uses GPU computation, not merely that a GPU appears in a device list.

Do not assume stock Ollama will accelerate this card on Windows: the [current Ollama hardware page](https://docs.ollama.com/gpu) lists the 9070 XT for Linux but omits it from its Windows ROCm support table. Recheck when implementing; support changes.

Resource starting points, to verify on your machine:

- One model process and one request at a time. Generate the complete answer dataset, stop that model, then load the judge and score saved outputs.
- Start with an 8,192-token context, about 3,000 generator tokens of evidence, and at most 768 output tokens. Check the entire prompt plus reserved output using the generator tokenizer.
- Q4 model files are roughly a few GB for 4B and around 5 GB for 8B; runtime memory also includes context/KV cache and working buffers. Measure both RAM and VRAM.
- Run embeddings on CPU in small batches, initially 16. Start with four CPU threads and benchmark; avoid starving the desktop.
- Keep approximately 25–40 GB free for models, environment, corpus, and reports. This is a working allowance, not a minimum specification.
- Close memory-heavy applications during full evaluations. A future 32 GB RAM upgrade would improve headroom, but buying hardware is not a prerequisite.
- Native Windows first. Docker, WSL, Kubernetes, and GPU-enabled Python are unnecessary for the initial system.

The [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) covers its local API and schema-constrained output. Validate actual capabilities against the pinned build. Use non-thinking mode for bounded structured responses; choose greedy decoding or a fixed seed for repeatability, then measure its quality. These settings do not guarantee identical GPU outputs across builds or machines.

## 3. Corpus and demonstration service

Use a selected snapshot of the official [FastAPI English documentation](https://github.com/fastapi/fastapi/tree/master/docs/en/docs). Pin a Git commit and an explicit file allowlist. Preserve the project's [MIT licence](https://github.com/fastapi/fastapi/blob/master/LICENSE) and attribution; check any separately licensed included material.

Cover request validation, response models, dependencies, authentication concepts, middleware, errors, testing, and deployment. Resolve documentation includes and code snippets from that same commit. A Markdown file containing an unresolved include is not a complete source. Exclude translations and duplicate navigation.

Write runbooks for a fictional local service, clearly labelled as your own examples: health endpoint, simulated dependency outage, log error codes, safe configuration fields, request timeout, and version compatibility. Runbooks must describe implemented behaviour. Generic framework docs cannot establish whether your particular service is healthy.

The service should expose fixed diagnostic endpoints and a few deterministic scenarios such as healthy, dependency unavailable, and configuration mismatch. Label its telemetry as simulated; you are demonstrating integration and controls, not diagnosing production infrastructure.

Keep old-version, contradictory, malicious, and restricted documents in explicit test fixtures or labelled corpus partitions. Never present authored facts as upstream FastAPI behaviour.

Document metadata:

```text
doc_id, source_repository, source_commit, relative_path, source_url,
licence, content_sha256, product_version, authority, access_roles,
heading_path, normalised_text, normalised_text_sha256
```

Chunk metadata adds a stable chunk ID, parent document ID, normalised character offsets, source-line mapping, and chunker version. Derive IDs from document identity, source revision, offsets, and chunker version. Preserve immutable snapshots so a citation remains inspectable after an index rebuild.

## 4. Runtime pipeline

```mermaid
flowchart TD
    Q[Question and authenticated identity] --> P[Validate request and policy]
    P --> R[Retrieve only authorised current-version evidence]
    R --> F[Fuse, deduplicate and budget context]
    F --> D[Bounded diagnostic proposal when needed]
    D --> T[Host validates and executes allowlisted tool]
    T --> G[Generate structured answer or abstention]
    G --> V[Validate schema and citation integrity]
    V --> S[Check claim support in strict mode]
    S --> O[Return answer, evidence and trace ID]
```

The diagnostic path is skipped when unnecessary. Every request traverses the same controller; a policy rejection can terminate early. Running the complete pipeline means executing its real control flow, not forcing generation or tools after an intentional refusal.

Implement `answer_question(request, services) -> PipelineResult`. CLI, API, and evaluation code call this same function. Evaluation labels and reference answers must never enter its inputs.

1. **Validate and authorise.** Bound question length, validate requested version, establish roles from server-owned identity, and create a trace ID. User text cannot grant itself access.
2. **Retrieve.** Apply role/version filtering before ranking both lexical and dense candidates. Start with top 20 from each, fuse using RRF with an initial constant of 60, and deduplicate overlapping passages. Use stable chunk IDs to break ties.
3. **Select context.** Initially pass up to six diverse chunks, within the actual generator-token budget. Save both the candidate ranking and the exact passages included in the prompt. Scores are not probabilities; tune evidence thresholds on development data.
4. **Collect diagnostics if needed.** The model may propose an action in a separate structured planning step. Host policy decides whether to execute it. Maximum two calls, no recursive agent loop.
5. **Decide and generate.** Return a supported answer, a clarification, or an abstention. State explicitly when the available sources cannot establish an answer. A popular fact memorised by the model is not evidence from the corpus.
6. **Validate.** Enforce schema, citation membership, quote offsets, access rules, version rules, and citation coverage. Allow at most one repair for malformed structure. Persistent failure returns a controlled error, with no unvalidated draft shown.
7. **Verify support in strict mode.** Make a separate local verifier call using the answer and its cited evidence, without reference answers. Unsupported or uncertain factual claims cause abstention; verifier failure produces a service error. Initially reuse the 4B model in a separate request, recognising correlated mistakes. Keep strict mode enabled for the release profile and include its latency. Evaluate whether it helps using an ablation.
8. **Return and record.** Render factual prose from validated claim objects, attach source excerpts, and record stage timings and decisions. Avoid free-text additions that bypass checks.

Recommended response contract:

```json
{
  "status": "answered",
  "reason_code": null,
  "claims": [
    {
      "id": "claim-1",
      "text": "The demo service request timeout is 30 seconds.",
      "citations": [
        {"evidence_id": "ev-1", "start": 80, "end": 110, "quote": "..."}
      ]
    }
  ],
  "trace_id": "..."
}
```

The values above illustrate the shape; real offsets must select the actual quote. Use statuses `answered`, `abstained`, `needs_clarification`, `policy_refused`, and `error`, with distinct reason codes. Abstentions contain no speculative factual answer.

For a first release, require all requested material facts to be supportable; otherwise abstain or request clarification. This makes partial-answer scoring and behaviour unambiguous. A later release may introduce explicitly evaluated partial answers.

### Deterministic citation validation

For every citation, prove that:

- Its evidence ID belongs to this request's authorised, actually supplied evidence bundle.
- Its source revision and text hash match the persisted snapshot.
- Offsets are in range and `evidence_text[start:end] == quote`, using a documented Unicode character-offset convention and normalisation policy.
- Its version, access metadata, and evidence type are valid for the request.
- Every rendered factual claim has at least one citation and no additional uncited factual prose is introduced by rendering.

Resolve URLs and source locations from the server's manifest, not model-generated URLs. For tools, cite an immutable evidence envelope containing tool name, validated arguments, scenario, timestamp and sanitised output hash. Mark live observations separately from documentation and reject stale observations according to the configured TTL.

**A valid quote can still be irrelevant or misleading.** These checks prove provenance and structure. Semantic support needs a separate judgment.

## 5. Safe diagnostic tools and security boundaries

Implement these as typed Python functions behind a broker:

| Tool | Allowed arguments | Output |
|---|---|---|
| `get_service_health` | A fixed service-ID enum | Selected status fields from one configured local endpoint |
| `get_recent_errors` | Same service enum, bounded limit of 1–20 | Sanitised structured records from a fixed source |
| `get_config_summary` | Same service enum | Explicitly allowlisted, non-secret configuration fields |

The model never supplies executable commands, file paths, arbitrary URLs, SQL, or credentials. Service IDs map to fixed destinations in host configuration. No redirects, arbitrary ports, or network discovery. Give each call a two-second timeout, output-size cap, and schema validation. Failed tools do not authorise guessed results.

Security controls and their tests:

- **Indirect prompt injection:** treat documents and tool output as untrusted data, delimit them, and instruct the model accordingly. Test malicious retrieved text and forged system messages. The hard boundary is the host tool/access policy. Prompts alone are insufficient; [OWASP describes RAG's remaining injection risk](https://genai.owasp.org/llmrisk/llm01-prompt-injection/).
- **Access control:** start with reader/operator roles and synthetic restricted runbooks. Filter before ranking, recheck before tool execution and response, and partition caches by identity/roles, version, corpus and tool scenario. Test guessed IDs and cross-role cache reuse. Restricted titles, counts and snippets must not leak.
- **Tool privileges:** require the operator role for diagnostics. The model's proposal is never permission. Assert zero forbidden calls, even when a malicious source requests them.
- **Local exposure:** bind app and inference servers to `127.0.0.1`; use narrowly allowed browser origins and an application token for diagnostic access. Identity is mapped by the server. Keep inference-server built-in agent/shell tools disabled.
- **Ingestion:** accept only configured source types and manifest paths. Reject traversal, absolute/UNC paths and symlink/junction escapes. Bound document size and nesting; never execute code from documents or enable remote model code.
- **Secrets and rendering:** use synthetic canary secrets in tests, never real credentials. Redact at collection time, keep secrets out of indexes, escape HTML and render snippets inertly. Do not log auth headers or raw environment variables.
- **Supply chain:** lock dependencies, pin model/corpus revisions and binary hashes, retain licences, run dependency and secret scans, and check downloads against publisher digests where available.
- **Resource abuse:** bounded input, output, tool count, queue and deadline; return controlled busy/timeout responses.

Write `docs/threat-model.md` covering assets, attackers, trust boundaries, controls and residual risks. State that these are tested controls within this demo scope; a finite attack suite does not prove universal injection resistance.

## 6. Failure handling

| Condition | User-visible result | Internal evidence |
|---|---|---|
| No relevant authorised evidence | Abstain: sources do not establish the answer | Retrieval scores and selection reason |
| Ambiguous version/question | Ask one targeted clarification | Ambiguity reason code |
| Conflicting authoritative passages | Explain the conflict with citations; do not resolve by guessing | Both passages and version metadata |
| Tool forbidden | Policy refusal | Broker denial; zero tool execution |
| Tool unavailable or stale | Say the current state cannot be determined | Tool error/timestamp; no fabricated observation |
| Model timeout/unavailable/OOM | Controlled service error | Stage, deadline, model/backend and sanitised error |
| Invalid JSON/citation after one repair | Controlled service error | Invalid draft retained only in protected trace |
| Unsupported claim in strict verification | Abstain | Verifier decision and cited evidence |
| Verifier unavailable | Controlled service error | Never mark this as successful abstention |
| Corrupt/mismatched index | Fail readiness; request rebuild | Manifest mismatch |
| Queue full | Bounded busy response | Queue/deadline metric |

Set explicit stage deadlines and one total request deadline, initially 90 seconds. Retry only specified transient read-only failures and keep retries within that deadline. Never fall back to an ungrounded answer when retrieval or tools fail.

Record stage-level latency, input/output tokens, repair count, tool decisions, final status, and model/runtime versions. Distinguish operational errors from knowledge abstentions in both the UI and metrics.

## 7. Evaluation dataset

Create 20 hand-reviewed cases before substantial tuning, then grow to **150 cases**:

| Slice | Count | Examples |
|---|---:|---|
| Single-source answerable | 40 | Exact settings, API names, prerequisites |
| Multi-source answerable | 25 | Combine configuration and deployment guidance |
| Unanswerable | 30 | Absent feature, unknown service fact, unavailable version |
| Ambiguous/conflicting | 15 | Unspecified version, conflicting runbooks |
| Diagnostic | 20 | Healthy/unhealthy scenarios, unavailable tool, denied role |
| Adversarial/access control | 20 | Injection, fake citations, canary leakage, forbidden tools |

Slices are reporting tags, not necessarily answerability labels. Every case also has a reviewed expected status; diagnostic and adversarial cases can be answerable or unanswerable.

Split 90 development / 60 held-out cases, stratified across slices. Group near-duplicate questions, document topics and paraphrase families together to limit leakage. All allowed corpus documents remain indexed in both splits. Holdout refers to evaluation questions and labels, not automatically unseen documents. Tune prompts, cutoffs and thresholds on development cases; freeze before holdout evaluation. Keep a separate judge-calibration set.

For each case store:

```yaml
id: runbook-timeout-001
question: What is the demo service request timeout?
identity_fixture: reader
product_version: demo-v1
scenario: healthy
expected_status: answered
answerable: true
reference_answer: The request timeout is 30 seconds.
required_facts:
  - id: timeout
    validator: duration_equals
    value_seconds: 30
forbidden_facts:
  - id: incorrect_timeout
    validator: duration_equals
    value_seconds: 60
gold_evidence_groups:
  - alternatives:
      - doc_id: demo-runbook-timeouts
        source_revision: pinned-demo-v1
        section: Request timeout
        quote: The request timeout is 30 seconds.
expected_tool_calls: []
tags: [single_source, numeric]
```

This is an authored demo fact, not a FastAPI default. Resolve gold spans against actual corpus snapshots during dataset validation. Require every gold evidence group for multi-hop questions; alternatives within a group are interchangeable. Anchor gold evidence to documents and spans rather than current chunk IDs so chunking experiments remain comparable.

Use deterministic validators for numbers/units, identifiers, required sets, negation-sensitive cases, and structured fields. A keyword appearing inside a refusal or contradicted sentence must not count as fact correctness. For open-ended cases, use reviewed atomic facts and semantic grading; do not pretend a substring check proves understanding.

Humans must check answerability against the authorised full corpus and tool scenario, not merely the first retrieved results. An answerable case where retrieval fails remains a system failure. An LLM may draft questions, but manually verify and diversify them.

## 8. Evaluation execution: the requested full flow

Use a two-phase run so generation and judging do not need to coexist in memory. These CLI commands are **interfaces to implement**, not tools already installed:

```powershell
python -m evidenceops.ingest --manifest corpus/manifest.yaml
python -m evidenceops.eval generate --dataset eval/holdout.jsonl --run runs/release-001
python -m evidenceops.eval score --run runs/release-001 --judge-config configs/judge.yaml
python -m evidenceops.eval gate --run runs/release-001 --thresholds eval/thresholds.yaml
```

Generation calls the complete production pipeline for every case. Diagnostic scenarios are supplied through the same tool broker. Save the generated answer and exact retrieved/selected evidence before scoring. Strict runtime verification is part of generation; the offline judge is a separate evaluation role.

Illustrative orchestration, not implementation code:

```python
validate_dataset_and_manifests()
for case in dataset:
    request = request_from_question_identity_version_and_scenario(case)
    try:
        result = pipeline.answer_question(request)  # no gold/reference fields
    except Exception as exc:
        result = controlled_failed_result(exc)
    persist_case_atomically(case.id, result, evidence_bundle, trace)

stop_answer_server_and_load_judge()
for case in dataset:
    result = load_saved_result(case.id)
    deterministic = check_facts_schema_citations_tools_and_abstention(case, result)
    correctness = judge_reference_correctness(case, result)
    support = judge_claims_against_their_cited_evidence(result)
    save_scores(case.id, deterministic, correctness, support)

report = aggregate_all_expected_cases_with_explicit_denominators()
save_json_markdown_and_junit_reports(report)
exit_nonzero_if_incomplete_invalid_or_required_threshold_missed(report)
```

### Per-run artifacts

```text
runs/<run-id>/
  manifest.json          # Git SHA, dirty status, corpus/index hashes, config hashes,
                         # model files/hashes, prompts, judge rubric, seed,
                         # runtime/backend/driver, hardware and dataset hash
  cases/<id>.json        # question, identity fixture, raw and validated output,
                         # candidates, selected evidence text/offsets/hashes,
                         # tool proposals/results, verifier, timings and errors
  scores.jsonl           # deterministic and semantic outcomes per case/claim
  metrics.json           # aggregates, denominators, slices, confidence intervals
  report.md              # pass/fail, differences, failures, limitations
  junit.xml              # machine-readable gate results
```

Keep raw artifacts local by default. Publish only sanitised examples and aggregate results. Write incrementally and atomically so a crash preserves completed cases. Resume only under an identical manifest; preserve original failures and any retry history. A new release run must not silently reuse old generated answers or retrieval results.

### Semantic correctness and claim support

Make two separate judge tasks:

1. **Reference correctness:** give the question, reviewed reference, required facts, and generated answer. Grade atomic fact coverage, contradictions, and materially wrong additions. Use a simple rubric: 0 wrong, 1 materially incomplete, 2 correct. An answerable case passes only with 2 plus its deterministic checks.
2. **Evidence support:** give each factual claim and its cited passages/tool evidence. Label `supported`, `contradicted`, or `insufficient`, and require evidence IDs plus a short rationale. The reference answer must not be used as evidence for this task. If a claim cites multiple passages, check their joint support.

Run an additional extraction/audit pass over all rendered text, including code blocks, to detect material claims omitted from the model's claim list. Compare that inventory to declared claims. No automatic extractor guarantees completeness; manually audit a sample and report misses.

Keep judge inputs as untrusted data, use a fixed rubric and schema, and include adversarial judge-manipulation examples. Invalid judgments/timeouts are evaluation errors, never passes. One bounded retry for malformed output is acceptable; record it and fail if unresolved.

Use the 8B judge as an initial evaluator, with thinking disabled and bounded output. It shares a model family with the generator, so correlated mistakes remain possible. A different-family local judge is a useful later comparison if resources allow. A larger judge is not automatically accurate.

Before trusting it, hand-label at least 60 balanced claim/evidence examples: direct support, negation, wrong numbers, missing prerequisites, conflicting versions, irrelevant quotes and injection. Separate calibration tuning from a validation subset. Report a confusion matrix, support/unsupported precision and recall, macro-F1, and repeated-run disagreement. Set an initial validation requirement of macro-F1 >= 0.80 and recall for unsupported/contradicted claims >= 0.85. If missed, improve the judge/rubric or require human review; do not present its scores as reliable automated release gates.

Do not use embedding similarity or a judge's uncalibrated confidence score as proof of correctness. The [Ragas paper](https://arxiv.org/abs/2309.15217) motivates separating retrieval and generation evaluation; [LLM-as-a-judge research](https://arxiv.org/abs/2306.05685) also documents judge biases. Implement transparent task-specific checks first; an evaluation library is optional later.

## 9. Metrics and required quality gates

The following are **proposed v1 targets**, not measured results or promised hardware performance. Establish a baseline, decide acceptable product targets on development data, commit thresholds, then evaluate holdout. Threshold changes require an explicit documented reason; never lower them silently to make a failing run green.

| Metric | Definition / denominator | Initial target |
|---|---|---:|
| Evidence-group recall@6 | Mean fraction of gold evidence groups covered by the six supplied passages, answerable cases with document gold | >= 0.85 |
| All-evidence success@6 | Fraction of those cases where all gold groups are covered | >= 0.75 |
| MRR@10 | Reciprocal rank of first relevant document passage; document-answerable cases | >= 0.75 |
| Required-fact accuracy | Correct required facts / expected required facts, macro-averaged by answerable case; abstentions/errors score 0 | >= 0.85 |
| Reference correctness pass rate | Fully correct answerable cases / all answerable cases; abstentions/errors fail | >= 0.80 |
| Citation integrity | Valid citation objects / all citation objects; missing mandatory citations also fail case checks | 1.00 |
| Declared-claim citation coverage | Answered declared factual claims with citations / all answered declared factual claims | 1.00 |
| Claim-inventory coverage | Material claims represented in validated claim list / audited material claims | >= 0.95 |
| Claim support | Judge-supported claims / all evaluated factual claims; contradicted/insufficient score 0 | >= 0.95 |
| Correct grounded-answer rate | Answerable cases passing facts, correctness, citation and support checks / all answerable cases | >= 0.75 |
| Unanswerable abstention recall | Correct knowledge abstentions / ground-truth unanswerable cases | >= 0.90 |
| Abstention precision | Correct knowledge abstentions / all knowledge abstentions | >= 0.90 |
| False-abstention rate | Knowledge abstentions / answerable cases | <= 0.10 |
| Expected-status accuracy | Exact expected status / all cases, with error never counting as abstention | >= 0.90 |
| Critical security violations | Forbidden tool executions, restricted disclosure, canary leaks | 0 |
| Unexpected pipeline errors | Unexpected errors / cases outside deliberate fault tests | 0 |
| Judge completeness | Cases/claims scored successfully / all expected scoreable cases/claims | 1.00 |
| Warm end-to-end p95 | Full answer pipeline including strict verification and tools; standard PC profile, concurrency 1 | <= 60 s, provisional |

For tool-only cases, evaluate tool observation coverage and expected calls separately; document recall is N/A. For cases mixing documentation and diagnostics, require both evidence types. For ambiguous and policy cases, score the expected status separately from knowledge-abstention metrics.

Report document retrieval both before and after context budgeting so truncation failures are visible. Collapse overlapping chunks matching the same gold group; duplicated passages cannot inflate recall. MRR is supplementary and does not establish multi-hop completeness.

Compute support as micro and per-answer macro averages. Report support conditional on answered cases alongside the grounded-answer rate over all answerable cases, so a system cannot win by refusing everything. Show the full answerability/status confusion matrix and per-slice results, especially multi-source, diagnostic, and adversarial performance.

Use explicit counts and denominators. An empty required slice, missing case, duplicated case ID, non-finite score, judge error, or missing artifact makes the release run incomplete and fails the gate. N/A is allowed only for predeclared inapplicable metrics. No vacuous 100% for zero claims or citations.

Report uncertainty: bootstrap intervals grouped by question family for aggregate quality, and Wilson intervals for simple proportions. Small holdout slices support limited conclusions; zero observed security failures means only zero in the tested cases.

Measure cold startup separately. Warm up once, disable answer-result caching for benchmarks, retain normal resident index/model caches, use a monotonic clock, and report p50/p95 plus timeout/error counts. Record failure durations rather than dropping them. Judge scoring time and total evaluation time are separate from user-facing latency. Freeze the latency gate after a hardware baseline; compare only matching profiles.

## 10. Automated tests and CI

### Layer A: deterministic tests on every pull request

Use fixed fixtures, fake model responses, fake clocks and controlled tools. Assert contracts and invariants; do not require a real model to repeat an exact paragraph.

Required tests:

- Ingestion is idempotent; includes resolve; changed sources invalidate indexes; offsets and hashes are correct.
- No chunk exceeds the embedding limit including headers; context selection respects the generator budget.
- Known lexical/vector fixtures retrieve expected passages; RRF tie-breaking is stable; access/version filters run before ranking.
- Citation validator rejects fabricated IDs, valid quotes from unselected chunks, wrong offsets, stale snapshots, and uncited claims.
- Correctness validators handle units, negation and forbidden values, rather than matching keywords indiscriminately.
- Controller handles no evidence, conflict, malformed JSON, timeout, OOM, tool denial and failed verification with the correct status.
- Broker blocks arbitrary URLs, shell-like arguments, unknown service IDs, excessive calls and out-of-range limits; denial occurs before side effects.
- Restricted evidence cannot appear in candidates, prompt context, response, logs or another role's cache.
- Canary secrets never escape; hostile HTML/code displays inertly.
- Evaluator handles every case, preserves failures, rejects missing scores, and produces correct denominators.
- Gate boundaries pass/fail correctly. Deliberately degrade retrieval, citation integrity and abstention labels in report fixtures and prove each required gate exits nonzero.

Run pytest, formatting/linting, dependency and secret scanning. Pin third-party CI actions, minimise token permissions, and upload sanitised reports even when a gate fails.

### Layer B: local integration and live model smoke tests

Run real ingestion, embeddings, retrieval, generator, verifier and tool broker on a 10–20-case smoke set. Include answerable, unsupported, diagnostic and malicious cases. Check useful behaviour and invariants, not exact generated text. Windows integration tests catch path and runtime differences absent from Linux CI.

### Layer C: full local semantic release gate

Run all cases through the live complete pipeline, then the offline judge, aggregation and gate. Run again before releases and after model, prompt, chunking, embedding, retrieval, tool-policy, or verifier changes. Repeat selected stochastic cases three times to measure instability; do not cherry-pick the best run.

GitHub-hosted deterministic tests do not prove semantic quality. A small optional CPU model smoke job can exercise live inference, but its latency and model profile are separate from the PC release evaluation.

For automated local execution, provide a PowerShell release script that runs tests, generation, scoring, report generation and gating, preserving a nonzero exit code from every stage. It is a local release gate, not automatically a GitHub branch-protection check.

If you later require a GitHub semantic status, use a trusted private automation repository and a dedicated isolated runner, or an appropriate hosted runner. Recompute on the exact reviewed project commit and bind the status/artifacts to that SHA. Do not run public pull-request code on your everyday Windows PC: [GitHub explicitly warns about public repositories and self-hosted runners](https://docs.github.com/en/actions/reference/security/secure-use). Keep the public project CI on hosted runners initially. A submitted old report is not a fresh semantic evaluation.

## 11. Repository layout

```text
evidenceops/
  README.md
  LICENSE
  THIRD_PARTY_NOTICES.md
  pyproject.toml
  dependency lock file
  configs/                 # app, model, judge, retrieval and release profiles
  src/evidenceops/
    api.py
    cli.py
    pipeline.py            # shared application entry point
    schemas.py
    ingest/
    retrieval/
    generation/
    citations/
    verification/
    policy/
    tools/
    eval/                  # generate, score, aggregate, report, gate
  demo_service/            # fixed simulated health/error scenarios
  corpus/
    manifest.yaml
    runbooks/
  eval/
    dev.jsonl
    holdout.jsonl
    judge_calibration/
    thresholds.yaml
  tests/
    unit/
    integration/
    security/
    fixtures/
  scripts/
    setup.ps1
    start-local.ps1
    evaluate.ps1
  docs/
    architecture.md
    threat-model.md
    evaluation-methodology.md
    failure-analysis.md
    hardware-baseline.md
  reports/                 # selected sanitised release reports
  .github/workflows/ci.yml
```

Ignore downloaded models, virtual environments, raw corpus caches, indexes, credentials and unrestricted run artifacts. Keep compact licensed fixtures, manifests and reproduction instructions in Git. Avoid an orchestration framework initially: explicit functions make retrieval, tool policy and evaluation easier to inspect.

## 12. Milestones and exit criteria

### Milestone 1 — Establish the machine and first evidence path

Approximate time: 6–10 hours.

- Create the repository, environment, lock file and a minimal test job.
- Run a pinned 4B model locally; confirm GPU computation and record latency/RAM/VRAM.
- Ingest 20 documents, resolve their code includes and hand-label 20 questions.
- Retrieve evidence and produce one cited answer plus one honest abstention.

Exit: a CLI command produces saved output and source excerpts on your PC. Hardware problems are resolved before adding architecture.

### Milestone 2 — Reproducible ingestion and retrieval baseline

Approximate time: 8–14 hours.

- Add stable metadata, chunk IDs, version/access filtering and exact span mapping.
- Compare lexical-only, dense-only and hybrid retrieval on the same development cases.
- Save rankings, context bundles and recall metrics. Add deterministic ingestion/retrieval tests.

Exit: rebuilds are traceable; retrieval failures can be inspected before generation.

### Milestone 3 — Structured answers, refusal and controlled tools

Approximate time: 12–18 hours.

- Add typed answer statuses, citations, bounded repair and strict support verification.
- Implement the demonstration service and three read-only diagnostic functions.
- Add host policy, role fixtures, deadlines, errors and malicious-source tests.

Exit: supported questions have valid evidence; unsupported questions abstain; forbidden diagnostics never execute.

### Milestone 4 — Semantic evaluation and reports

Approximate time: 14–22 hours.

- Expand and review the dataset; separate development, holdout and calibration sets.
- Implement the two-phase evaluation runner, fact checks, judge tasks and calibration.
- Aggregate all required metrics; generate JSON, Markdown and JUnit reports.
- Prove missing results and deliberately bad metrics fail the gate.

Exit: one command runs the requested full evaluation flow and returns a meaningful exit code.

### Milestone 5 — Measured improvements and security review

Approximate time: 12–20 hours.

- Inspect actual failures. Change one factor at a time: chunk size, retrieval fusion, evidence count, verifier, prompt or model.
- Compare the baseline and candidate on identical cases and settings. Try a reranker only if retrieval errors justify its extra memory/latency.
- Freeze the release configuration and thresholds; run holdout and repeatability checks.
- Finish the threat model, sanitisation checks and Windows setup rehearsal.

Exit: a reproducible comparison explains both improvements and remaining failures.

### Milestone 6 — Present it as engineering work

Approximate time: 8–12 hours.

- Add a modest evidence-viewing interface if useful; keep the CLI as a reproduction path.
- Record a 2–3 minute demo: supported answer, unsupported refusal, diagnostic call, injected attack, and a failing quality gate.
- Publish sanitised reports, architecture, setup and an honest limitations section.
- Reproduce from a clean environment and tag the tested commit.

Exit: a reviewer can understand the problem, run a small example, inspect evidence and verify the reported measurements.

## 13. Experiments and GitHub presentation

Keep a results table with actual values, sample counts and matching run manifests:

| Experiment | Evidence recall@6 | Grounded-answer rate | False abstention | Warm p95 | Conclusion |
|---|---:|---:|---:|---:|---|
| Lexical baseline | To measure | To measure | To measure | To measure | Establish baseline |
| Dense baseline | To measure | To measure | To measure | To measure | Inspect terminology misses |
| Hybrid retrieval | To measure | To measure | To measure | To measure | Measure fusion benefit |
| Hybrid + strict verifier | To measure | To measure | To measure | To measure | Quantify safety/coverage/latency tradeoff |
| Optional reranker or 8B generator | To measure | To measure | To measure | To measure | Keep only if worthwhile |

Include at least five analysed failures with a cause and attempted fix: missing evidence, misleading quote, wrong version, excessive refusal, and diagnostic failure. Record regressions and tradeoffs as well as improvements. Avoid describing a lightly tested demo as production-ready.

Potential CV bullet after completion, replacing placeholders with measured values:

> Built a local documentation and diagnostics assistant with hybrid retrieval, source-verified citations, role-controlled tools and automated quality gates; evaluated on [N] reviewed questions, achieving [X]% grounded-answer success and [Y]% unsupported-question abstention recall at [Z]s warm p95 latency on an RX 9070 XT.

Do not put planned metrics on your CV as achieved results. The strongest interview discussion will explain how you separated retrieval errors from answer errors, validated your judge, prevented forbidden tool execution, and handled the cases your system could not answer.

## 14. First practical session

1. Create a public-ready repository and write a one-paragraph problem statement.
2. Establish native local inference and record the exact working software/hardware configuration.
3. Select 20 documentation pages plus one authored runbook and pin their revisions.
4. Write ten answerable, five unanswerable, three diagnostic and two adversarial questions, with reviewed evidence and expected statuses.
5. Build lexical retrieval and inspect its results before adding dense retrieval.
6. Connect the generator, return claim-level citations, and save every run.
7. Add deterministic citation tests and a basic report before expanding the corpus.

The first goal is a small trustworthy vertical slice. Expand its corpus, controls and measurement until it meets the release criteria above.
