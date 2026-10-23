# Improvement 1: reducing false refusals with exact-excerpt citation repair

Date: 23 October 2026  
Project: EvidenceOps — local documentation assistant  
Baseline: `dev-baseline-001`  
Candidate: `dev-citation-repair-001`

## Outcome

Changing the citation-repair step removed both false refusals in the fixed 20-question development evaluation. The assistant answered all ten answerable questions, continued to abstain on all ten unsupported requests, and retained 100% exact citation integrity for emitted answers. The required development gate changed from FAIL to PASS.

This measures behaviour on a small development set used to diagnose the problem. It does not establish 100% semantic accuracy or generalisation to unseen questions.

## What the first evaluation revealed

The initial evaluation contained:

- Ten answerable documentation/specification questions.
- Five questions whose answers were absent from the corpus.
- Three diagnostic requests the application could not fulfil because tools were not implemented.
- Two malicious user-input attempts asking for invented secrets or citations.

The baseline answered eight of the ten answerable questions. It refused these two despite retrieving the expected evidence:

1. “What import statement provides TestClient from FastAPI?”
2. “What does CORS stand for?”

The false-abstention rate was therefore `2 / 10 = 20%`, above the required maximum of 10%. The evaluation correctly returned a failing exit code.

Retrieval recall alone did not explain the failures: all ten answerable cases had their gold evidence in the selected top-three passages. We needed to inspect the saved intermediate outputs.

## How we diagnosed the cause

Each case record retained the retrieved passages, initial invalid draft, repair count, final draft, verification results and final status. Inspecting these records showed the following sequence:

```text
Relevant evidence retrieved
    -> model proposes the requested answer
    -> its quote fails deterministic validation
    -> one repair attempt runs
    -> the repaired response abstains
```

For **TestClient**, the initial claim named the correct import, but its quote combined text that was not contiguous in the cited passage. A citation must point to an actual exact excerpt; combining separate fragments into one quotation is invalid.

For **CORS**, the initial claim gave the correct expansion, but the selected evidence ID did not contain the quoted heading. Text existing somewhere in the corpus is insufficient: it must exist in the particular retrieved passage being cited.

The original validator correctly rejected both citations. The weakness was the repair interface: it asked the model to transcribe evidence again, and the model chose to abstain instead.

This refined our first diagnosis. The final outputs were false refusals, but the initial drafts already contained the requested answers. The failure occurred during citation construction and repair.

## The change

We changed the single bounded repair attempt to use **host-prepared exact excerpts**.

1. The application extracts non-empty lines from the retrieved passages.
2. Each available excerpt receives a temporary quote ID, such as `Q0`.
3. The repair model returns a claim and selects a quote ID. It does not return replacement quote text.
4. The application resolves that ID to the original excerpt and its evidence ID.
5. The existing deterministic citation validator checks the resolved answer.
6. The existing semantic support verifier checks whether the quote actually supports the claim.
7. Only an answer that passes those checks is rendered. Otherwise the existing refusal/error behaviour applies.

The repair response has this shape:

```json
{
  "status": "answered",
  "claims": [
    {
      "text": "The answer supported by the selected excerpt.",
      "quote_id": "Q0"
    }
  ]
}
```

`Q0` is illustrative, not a permanent citation. IDs are generated from the evidence selected for that request. The host supplies the final source text, evidence identity and quote offsets.

The implementation adds `quote_candidates()`, `repair_schema()` and `resolve_repair()` in `evidenceops.py`. Saved traces now also retain `repair_candidates` and `repair_response` so the repaired citation can be inspected.

The initial generation step still produces ordinary quoted citations. Exact-excerpt selection is introduced only when that draft fails validation. The maximum remains one repair attempt.

## Keeping the comparison meaningful

We retained the same:

- Twenty development questions, reference answers and labels.
- Pinned documentation corpus and chunking.
- Top-three lexical retrieval and its ranking.
- Required thresholds.
- Evaluation implementation and offline judge prompts.
- Recorded generator and judge model API identities.

`compare_runs.py` checks the saved identities and hashes and reports retrieval/status changes. There were no changes to retrieved passage rankings. The focused production change was the repair mechanism.

The original baseline results and judge labels were preserved. The exact baseline pipeline source is saved in `experiments/citation-repair/baseline_evidenceops.py`; its hash matches the original generation manifest.

## Results

| Measurement | Baseline | Candidate |
|---|---:|---:|
| Correct expected answer/abstention status | 18/20 | 20/20 |
| Answerable questions answered | 8/10 | 10/10 |
| False-abstention rate | 20% | 0% |
| Unsupported requests abstained | 10/10 | 10/10 |
| Gold evidence groups retrieved | 10/10 | 10/10 |
| Emitted citation integrity | 100% | 100% |
| Pipeline errors | 0 | 0 |
| Required-pattern check rate | 80% | 100% |
| Required development gate | FAIL | PASS |
| Observed p95 pipeline latency | 1,739.92 ms | 2,073.01 ms |
| Uncalibrated reference-correctness score | 60% | 80% |

“Answered” means the pipeline emitted an answer; it is not equivalent to an independently verified correct answer. Required-pattern checks are limited surface checks. Citation integrity establishes that quotations match their sources, not that every claim follows from those sources.

The candidate's observed p95 latency increased by approximately 333 ms. These were single runs with uncontrolled model caches, so this is an observed tradeoff rather than a controlled performance conclusion. The repaired cases now proceed to support verification instead of refusing earlier, which adds work.

## Automated verification and repeat checks

All **53 deterministic tests** passed after the change. Additional tests check that:

- A repaired quote is supplied exactly by the host.
- An invented quote ID is rejected.
- A repair response cannot override quote text.
- A valid selected excerpt still needs to pass semantic support verification.
- The repair count remains bounded.
- Comparisons reject changed datasets or model API identities and report retrieval differences.

The two fixed cases were also repeated three times each. All **six additional attempts** answered, passed citation integrity, and passed the limited required-pattern checks. Their records are stored in `runs/repair-repeatability`.

Those repeats provide a small consistency check, not evidence of robustness across arbitrary questions.

## What we learned about the judge

The offline correctness judge still rejected two unchanged answers concerning raising `HTTPException` and inheriting from `BaseModel`. Reviewing its reasons suggested excessive sensitivity to wording or completeness. These are assistant review findings that still need human adjudication; the original labels were not changed.

The generator, runtime verifier and offline judge currently use the same local 4B model. Their errors may be correlated. Semantic scores therefore remain explicitly uncalibrated and are not required quality gates. See `JUDGE_REVIEW.md` for the individual disagreements.

An exact excerpt can be irrelevant, incomplete, misleading, or malicious. Selecting excerpts solves quote transcription errors; it does not solve semantic grounding or prompt injection by itself.

## Reproduce and inspect

Run these individually from the `LLM_Project` folder. Keep the local model server running for a new evaluation.

Run deterministic tests:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

Compare the preserved runs:

```powershell
.\.venv\Scripts\python.exe compare_runs.py runs/dev-baseline-001 runs/dev-citation-repair-001
```

Run a fresh evaluation using the current pipeline:

```powershell
.\.venv\Scripts\python.exe evaluate.py run --judge
```

Check the saved candidate gate without rerunning inference:

```powershell
.\.venv\Scripts\python.exe evaluate.py gate --run runs/dev-citation-repair-001
```

Inspect these artifacts:

- `runs/dev-baseline-001/report.md`: original failing baseline.
- `runs/dev-citation-repair-001/report.md`: candidate report.
- `runs/dev-citation-repair-001/comparison.json`: recorded before/after comparison.
- Each run's `cases/` directory: exact questions, evidence, drafts and decisions.
- `runs/repair-repeatability/summary.json`: six repeat-check results.

Generated run records are ignored by Git. Select and sanitise any reports intended for GitHub publication.

## Limits and next steps

This improvement was developed after inspecting these same questions, so the results are development-set evidence. No held-out performance claim is justified yet. Source labels and judge disagreements still require human review. Exact model file hashes and a complete hardware/runtime manifest also remain to be added.

Next, review the labels, create a separate held-out question set, and build a balanced judge-calibration and validation dataset. Require semantic metrics only after measuring judge agreement against reviewed labels.

The engineering lesson is concrete: saved intermediate artifacts let us distinguish retrieval failures from citation-construction failures. Moving exact text handling into deterministic application code improved this development baseline while keeping the existing validation and support requirements intact.
