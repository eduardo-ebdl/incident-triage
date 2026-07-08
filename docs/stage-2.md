# Stage 2 - grounded resolution memory

Stage 2 replaces trace-only triage with suggestions grounded in past resolutions. The first
vertical slice is P8: a synthetic resolution corpus stored in Delta and indexed by Databricks
AI Search (formerly Vector Search).

## P8 resources

- Seed corpus: `data/resolution_memory.json`
- Source table: `observability.dev.resolution_memory`
- AI Search endpoint: `incident-triage-ai-search`
- Delta Sync index: `observability.dev.resolution_memory_index`
- Embedding endpoint: `databricks-qwen3-embedding-0-6b`
- Search mode: hybrid
- Sync mode: triggered

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

- P8 corpus and provisioner: implemented. The development checkpoint uses
  `workspace.default.incident_triage_resolution_memory` because the current account has only
  `USE SCHEMA` on `observability.dev`; moving the table and index there requires `CREATE TABLE`
  from the schema owner. The real hybrid-search checkpoint returned
  `synthetic-runbook/spark-join-oom` first for an OOM during a large Spark join.
- P9 LangGraph agent: not started.
- P10 retrieval fusion/reranking: not started.
- P11 grounding guardrail: not started.
