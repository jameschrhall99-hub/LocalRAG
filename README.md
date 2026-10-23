# EvidenceOps: first working slice

This is a small lexical RAG baseline for the project in Plan.md. Python 3.12+; no third-party Python packages. The current Python 3.14 environment can run it. Keep the existing llama.cpp Qwen3-4B server running on 127.0.0.1:8080 with thinking disabled per request.

From the LLM_Project folder, run these as individual single-line PowerShell commands (activation is unnecessary):

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

```powershell
.\.venv\Scripts\python.exe evidenceops.py "What is the request timeout in the fictional demo-v1 specification?"
```

```powershell
.\.venv\Scripts\python.exe evidenceops.py "What is the demo service administrator password?"
```

```powershell
.\.venv\Scripts\python.exe evidenceops.py "How do I raise an HTTP error in FastAPI?"
```

Each real question runs lexical retrieval, structured model generation, deterministic quote validation and a separate support-verifier call when an answer is proposed. Unsupported claims are withheld. Model/verification failures return error, not a successful knowledge abstention. Results include the question, retrieved text, hashes, draft, verdicts, validated citations and total latency in runs/<trace-id>.json. Raw traces can contain untrusted model text: inspect them as data and do not publish sensitive queries.

Evidence offsets are zero-based Python Unicode character positions in the exact stored passage; end is exclusive. The program derives offsets from exact quotes and renders only validated claim objects. The CLI returns exit code 1 for operational errors and 0 for answers/knowledge abstentions; these are not yet quality-gate exit codes.

## Corpus provenance

The four short passages are two original study-note summaries of official FastAPI documentation and two explicitly fictional policy/specification fixtures. They are not an ingested snapshot of upstream documentation. Original source URLs and revision labels are stored in corpus.json, with content hashes attached at runtime. The fictional service and diagnostics do not exist yet. Unknown questions must not be answered from model memory.

## Honest limits and next milestones

- This uses SQLite FTS5 BM25 over four complete short passages, rebuilding a tiny in-memory index per request. It is the lexical baseline, not hybrid retrieval or production ingestion.
- The generator and verifier use the same model and can make correlated mistakes. Exact quotes do not prove support. The verifier has not been calibrated, and no semantic quality percentage is claimed.
- There is no FastAPI application endpoint, role enforcement, tool execution, independent offline judge or release quality gate yet. The only application interface is the CLI. The inference endpoint is fixed to localhost; question text cannot select another URL.
- The tests use fake model responses and check contracts, citation rejection, abstention and failure behaviour. They do not establish real-model quality.
- Next: ingest pinned original documentation with resolved includes; expand to 20 reviewed questions; add a dataset runner and explicit metrics; then dense retrieval, API, safe diagnostics and the independent judge described in Plan.md.
- Keep runtime outputs and downloaded models out of Git. Retain the existing Plan.md and llama.cpp directory.

The existing server startup command can include --cache-ram 0 to avoid a large RAM prompt cache on this 16 GB PC. The server must remain running while CLI questions execute.
