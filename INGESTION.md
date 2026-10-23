# First documentation snapshot

Leave the llama.cpp model server running for the final question, but ingestion itself does not call a model. No new Python packages are needed.

Run these one at a time from your LLM_Project folder:

```powershell
.\.venv\Scripts\python.exe ingest.py
```

The first run resolves FastAPI's master branch to a full Git commit and downloads 20 selected English tutorial pages, the MIT licence and their included code examples. It expands snippets as inert text, preserves source-line mappings, and generates overlapping passages of at most 1,800 characters. This is character-based lexical chunking; the embedding tokenizer budget will be introduced with dense retrieval.

The corpus/manifest.json file records the pinned commit and source hashes. Subsequent runs reuse that revision. An explicit --revision argument is accepted on a fresh snapshot; changing an existing pin is refused to prevent accidental dataset changes. Rebuild without downloading with:

```powershell
.\.venv\Scripts\python.exe ingest.py --offline
```

Run all deterministic tests:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

Ask a question using the new documentation automatically:

```powershell
.\.venv\Scripts\python.exe evidenceops.py "Should I raise or return HTTPException in FastAPI?"
```

The assistant now loads indexes/corpus.json when corpus/manifest.json exists; it refuses mismatched/corrupt artifacts instead of silently falling back. The original corpus.json remains available as test fixtures and fallback before the first successful ingestion. Two fictional service fixtures are retained in the new index; authored FastAPI summaries are excluded in favour of the upstream pages.

## Files to understand

- Track ingest.py, test_ingest.py, INGESTION.md, corpus/manifest.json and corpus/LICENSE.fastapi.txt in Git.
- corpus/cache/ holds cached sources and normalised documents with per-line provenance. indexes/ holds the generated passage index. Both are already ignored by .gitignore.
- Existing runs/ traces remain intact. New traces record the corpus hash, retrieved passages and their original source spans. Quote offsets remain relative to the exact selected passage; document_start plus quote start maps back to the normalised document.
- Original Markdown is retained rather than flattened into prose. Includes are resolved from the same commit. Unsupported directives fail ingestion explicitly; code is never executed.
- Hashes detect accidental changes; they do not authenticate a maliciously edited manifest. Sources are fetched over HTTPS from fixed GitHub hosts.

The next milestone is 20 manually reviewed questions and an evaluation runner. This ingestion step does not establish semantic accuracy, claim-support reliability, access control, safe diagnostic execution or CI quality gates. The same-model runtime verifier remains uncalibrated.
