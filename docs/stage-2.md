# Stage 2 - grounded resolution memory

Stage 2 replaces trace-only triage with suggestions grounded in past resolutions. The first
vertical slice is P8: a synthetic resolution corpus stored in Delta and indexed by Databricks
AI Search (formerly Vector Search).

## P8 resources

- Seed corpus: `data/resolution_memory.json`
- AI Search endpoint: `incident-triage-ai-search`
- Embedding endpoint: `databricks-qwen3-embedding-0-6b`
- Search mode: hybrid
- Sync mode: triggered

Current location (moved from the `workspace.default` dev checkpoint once `CREATE TABLE` on
`observability.dev` was granted):

- Source table: `observability.dev.resolution_memory`
- Delta Sync index: `observability.dev.resolution_memory_index` — verified `ONLINE_NO_PENDING_UPDATE`,
  18 rows indexed, hybrid search re-verified with the same top result (`spark-join-oom`, score `1.000`).

The earlier `workspace.default.incident_triage_resolution_memory(_index)` checkpoint was removed
on July 11 after the definitive resources were verified. No repository configuration points to it.

The committed corpus contains 18 synthetic error-resolution pairs. Each result has a stable
`resolution_id`, a resolution, and a synthetic source identifier that can later be enforced by
the P11 grounding guardrail.

## Provision

Install the optional dependencies:

```bash
pip install -e ".[databricks,rag]"
```

Set the Stage 2 variables shown in `.env.example`, then run:

```bash
python scripts/provision_ai_search.py
```

The script is idempotent. It creates the Delta source table with Change Data Feed enabled,
upserts the seed records, creates a standard AI Search endpoint if needed, and creates or
syncs the triggered Delta Sync index.

To seed only the Delta table:

```bash
python scripts/provision_ai_search.py --seed-only
```

## Local contract

`incident_triage.memory.search_past_resolutions()` accepts an injected index in tests, so the
retrieval contract remains verifiable without credentials or network access. Production calls
load `DATABRICKS_AI_SEARCH_INDEX` and query AI Search with `query_type="HYBRID"`.

For a direct smoke test:

```bash
python scripts/search_resolution_memory.py "OutOfMemoryError during a large Spark join"
```

## Stage 2 status

- P8 corpus and provisioner: implemented in the definitive `observability.dev` location. The real
  hybrid-search checkpoint returned `synthetic-runbook/spark-join-oom` first for an OOM during a
  large Spark join, with score `1.000`.
- **Retrieval wired into the triage call (P4).** `triage_incident` now calls
  `search_past_resolutions(error_message)` and passes up to 3 retrieved cases into the prompt.
  The model is instructed to only fill `suggested_fix`/`sources` when a retrieved case genuinely
  applies, otherwise leave both empty rather than force a match. Verified against the real table
  and index: 9 of 11 incidents came back with a grounded, cited fix; 2 (`AttributeError`,
  `AssertionError`) correctly came back empty because none of the retrieved cases matched.
  `_retrieve_grounding` degrades to an empty list (not an exception) when Stage 2 isn't
  configured, so Stage 1 keeps working standalone.
- Validation: 16 local tests passed, including the seed contract, AI Search response parsing,
  and grounding degradation without network access.
- P9 metadata preparation: `task_run_id` and `attempt_number` are populated in 46 of 65 current
  incident rows. `repair_history` and `libraries` remain empty; serverless cluster fields are
  expected to remain empty. The application does not consume these columns yet.
- P9 LangGraph agent: not started. What exists today is single-shot retrieval-augmented triage,
  not an agent that decides which tools to call or investigates in a loop.
- P10 retrieval fusion/reranking: not started.
- P11 grounding guardrail: not started as a hard check — today it is prompt instruction only
  ("don't force a match"), not an enforced, code-level verification that a citation is valid.
