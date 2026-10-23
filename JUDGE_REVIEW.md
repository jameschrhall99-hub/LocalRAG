# Review of the first judge decisions

These are assistant review notes, not an independently human-labelled calibration set. The original scores and baseline reports remain unchanged. The current 4B judge is uncalibrated and shares a model with generation.

## Raise versus return HTTPException

Question: Should I raise or return HTTPException in FastAPI?

Saved answer: You should raise `HTTPException` when you need to return an error to the client.

Saved supporting quote: Because it's a Python exception, you don't `return` it, you `raise` it.

The correctness judge rejected the answer for not explicitly saying “rather than return it.” My review: the answer directly selects raising the exception and matches the requested choice, so this looks like an overly strict completeness judgment. The quote also supports the distinction. A future human calibration review should label this case and test equivalent paraphrases.

## Request body BaseModel

Question: Which Pydantic class should a FastAPI request body model inherit from?

Saved answer: The Pydantic class should inherit from `BaseModel`.

The supporting code declares `class Item(BaseModel):`. The judge rejected the answer because the reference says the model inherits from Pydantic BaseModel, while the answer says the Pydantic class inherits from BaseModel. My review: “Pydantic class” is imprecise wording, but the selected superclass answers the question. This looks like a wording-sensitive rejection rather than a factual error. Human review should decide whether this level of imprecision is acceptable and record that rubric decision.

## Keep the experiment separate

The citation-repair candidate retains the original correctness and support judge prompts, dataset, retrieval, corpus and thresholds. Only the production citation-repair mechanism changes. This avoids attributing a higher judge score to an improved answer when the grader itself changed.

Do not turn semantic scores into required gates yet. Next, assemble an independent, balanced calibration/validation set with correct paraphrases, incomplete answers, wrong numbers, negation, irrelevant quotes and contradictions; review it with a human before using its measured agreement as a release criterion.
