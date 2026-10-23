# First development evaluation

This adds 20 source-checked development questions, deterministic checks, optional offline local-model judging, and a report gate. It is an initial baseline, not the complete release evaluation in Plan.md.

## Run it

Keep the Qwen3-4B llama.cpp server running. From LLM_Project, run these individually:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

```powershell
.\.venv\Scripts\python.exe evaluate.py run --judge
```

The second command runs all 20 questions through the same production answer_question function; gold labels and reference answers are never passed to it. Generation includes the existing runtime support verifier. It saves every answer, retrieved passage and error before evaluation. Offline scoring then checks facts/citations/abstention and makes separate calls for reference correctness and support of emitted claims.

Watch the printed progress. At the end it prints the path to runs/eval-.../report.md. Open that file to inspect the results. Exit code 0 means required development gates passed, 1 means a gate failed, and 2 means the evaluation was incomplete or invalid. A red gate is a useful baseline finding; do not lower thresholds to hide it.

To inspect the most recent exit code in PowerShell:

```powershell
$LASTEXITCODE
```

To run without the optional offline judge, omit --judge. The existing runtime verifier still runs because it belongs to the actual pipeline.

## Run generation and judging separately

Use a fresh run folder:

```powershell
.\.venv\Scripts\python.exe evaluate.py generate --run runs/baseline-001
```

```powershell
.\.venv\Scripts\python.exe evaluate.py score --run runs/baseline-001 --judge
```

```powershell
.\.venv\Scripts\python.exe evaluate.py gate --run runs/baseline-001
```

Separating phases lets you stop the generator server and start a different judge model on the same port before scoring, without loading both simultaneously. This update does not download or require an 8B model. Initially the 4B server serves both roles, so errors are correlated. Changing judge models requires recording that change; the report captures its API model identity.

## Dataset and measurements

eval/dev.json contains ten answerable cases, five absent-answer cases, three unavailable-diagnostic cases and two malicious user-input cases. Gold evidence uses document identities, revisions and quotes rather than current chunk IDs. Generation validates that every answerable gold group is actually present in the corpus. A gold group is recalled only if a selected passage contains a complete matching quote at the expected revision. Alternatives within a group are interchangeable.

References were checked against the pinned sources by the assistant; each case is explicitly marked pending human review. Read the question, reference and gold quote before treating the dataset as an independently reviewed benchmark. No held-out set has been created yet, and these cases are development data.

Deterministic metrics include evidence-group recall@3, limited required-pattern checks, exact citation/offset/hash integrity, expected-status accuracy, abstention recall/precision, false abstention, pipeline errors and total pipeline latency. Answers and abstentions remain separate from operational failures. Missing cases, empty denominators for required metrics, non-finite scores and changed artifacts cannot silently pass.

Required-pattern checks inspect rendered answer text; they are surface checks that can miss negation or be satisfied by a wrong sentence. They are explicitly not semantic correctness. Reference correctness is a separate optional judgment. Deterministic citation integrity proves provenance, not entailment.

Optional semantic metrics separately report reference correctness and cited-claim support. The judge's output must be structurally complete; judge timeouts or malformed responses fail completeness rather than becoming passes. Semantic quality thresholds are deliberately not required yet because the judge has not been calibrated. A development gate PASS therefore does not mean semantic release readiness.

Thresholds live in eval/thresholds.json and are snapshotted at generation time. For this top-three lexical baseline, the initial development targets are 0.8 retrieval/fact-pattern coverage, 1.0 citation integrity, 0.9 expected-status/unknown abstention, at most 0.1 false abstention and zero pipeline errors. These targets are set before the first run and may legitimately fail. Latency is reported without a gate until controlled hardware measurements exist.

## Saved run contents

- dataset.json and thresholds.json: exact evaluation inputs.
- manifest.json: dataset/corpus/code hashes, model API identity, Python version, completeness and case hashes.
- cases/<id>.json: question, actual output, exact evidence, runtime verification, latency and errors.
- scores.partial.json: incrementally saved evaluation judgments if a run is interrupted.
- report.json and report.md: case-level results, aggregates, slice summaries, limits and gates.

Hashes detect accidental drift, not a maliciously rewritten entire report. Full model file hashes, driver/backend versions, confidence intervals, JUnit output and CI integration remain future improvements. Runs stay ignored by Git; curate sanitised reports later. Gate enforcement recomputes aggregates from saved per-case scores and frozen thresholds rather than trusting a stored PASS flag.

Next: review the worst cases and judge mistakes, add a held-out question split and judge calibration set, then compare lexical retrieval against dense/hybrid retrieval with frozen evaluation inputs.
