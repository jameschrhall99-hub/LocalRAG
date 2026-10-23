# Experiment 1: repair quotes by selecting exact excerpts

## Problem found in the saved baseline

Both false refusals were citation-repair failures rather than missing retrieval. In the TestClient case, the initial answer named the correct import but combined non-contiguous source text into one quote. In the CORS case, the draft chose an evidence ID that did not contain the quoted heading. Exact validation rejected both. The previous repair prompt asked the model to copy the quote again; it chose abstention.

This refines the earlier diagnosis: the final drafts were refusals, but the initial drafts already contained the requested answers. The retained invalid_draft and repair_count fields exposed the actual path.

## One focused change

Initial generation, retrieval, source data, dataset, thresholds, support checking and offline judge prompts remain the same. Only the bounded repair interface changes.

On a validation failure, the app creates exact non-empty line excerpts from the retrieved passages and assigns temporary quote IDs. The model can select a quote ID and write a claim; it cannot supply replacement quote text. The host resolves the ID back to the exact source text and evidence ID. The existing citation validator and semantic support checker then run normally. There is still only one repair attempt.

This prevents quote transcription mistakes in repair; it does not establish that the selected quote supports the claim. A model can select an irrelevant excerpt, and the same-model support checker may miss that. New tests cover unknown IDs, attempted quote overrides and unsupported repaired claims.

## Baseline versus candidate

Both runs use the same 20-question development dataset, pinned corpus, top-three lexical retrieval, thresholds, evaluator and model API identities. compare_runs.py checks these recorded identities and reports passage-ranking changes. No retrieval changes occurred.

| Metric | dev-baseline-001 | dev-citation-repair-001 |
|---|---:|---:|
| Correct expected status | 18/20 | 20/20 |
| Answerable questions answered | 8/10 | 10/10 |
| False-abstention rate | 20% | 0% |
| Unsupported requests abstained | 10/10 | 10/10 |
| Gold evidence groups retrieved | 10/10 | 10/10 |
| Emitted citation integrity | 100% | 100% |
| Pipeline errors | 0 | 0 |
| Required development gates | FAIL | PASS |
| p95 pipeline latency | 1,739.92 ms | 2,073.01 ms |
| Uncalibrated reference correctness | 60% | 80% |

The latency values are observations from single runs with uncontrolled model caches, not a controlled benchmark. Citation repair now proceeds to support verification rather than refusing early, which adds work for those repaired cases.

The two fixed cases were additionally repeated three times each. All six attempts answered, passed exact citation integrity and passed the limited required-pattern checks. Their traces are retained in runs/repair-repeatability. This small repeat check does not establish general robustness.

## Judge review and limits

The offline correctness judge still rejects the unchanged raise-error and body-model answers for wording/completeness reasons. See JUDGE_REVIEW.md for assistant review notes. These appear to be questionable rejections, but a human should adjudicate them. Original judge labels and all original results remain untouched.

This is a development-set improvement after inspecting failures on those same questions. It is not held-out evidence or a claim of 100% semantic accuracy. Semantic quality gates remain disabled until independent calibration and validation. Model API identities are recorded; exact model binary hashes and full hardware/runtime manifests are not yet available.

## Reproduce and inspect

From LLM_Project with the model server running:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

```powershell
.\.venv\Scripts\python.exe evaluate.py run --judge
```

Compare the preserved fixed runs:

```powershell
.\.venv\Scripts\python.exe compare_runs.py runs/dev-baseline-001 runs/dev-citation-repair-001
```

The comparison writes comparison.json inside the candidate run. Its baseline gate remains FAIL and candidate gate PASS. experiments/citation-repair/baseline_evidenceops.py preserves the exact baseline pipeline source; its hash matches the old generation manifest. Running that snapshot in isolation requires the same corpus, fixtures and evaluator inputs.

Next: have a human review the development labels and judge disagreements, create a separate held-out set and balanced judge-calibration examples, and validate judge agreement before requiring semantic scores in release gates. Do not change the existing development labels to make scores look better.
