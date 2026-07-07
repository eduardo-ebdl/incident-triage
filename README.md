# Incident Triage Copilot — AI/ML side

Databricks job-failure triage copilot. Portfolio project built in a pair with a Data Engineer:
the DE owns fake failing jobs + ingestion into a Delta table; this repo is the AI/ML side that
reads that table, triages each failure with Claude, and sends a daily digest.

Full architecture spec and execution plan live outside this repo, in the author's private
career-planning vault (not published here).

## Status: Stage 1 (MVP digest)

Pipeline: read incidents → dedup → 1 Claude call per distinct error → aggregate by job/severity →
email digest. No RAG/agent loop yet — that's Stage 2.

## The seam

Table: `observability.dev.job_error_logs` (owned/populated by the DE's side).

## Setup

```
pip install -e ".[dev]"
cp .env.example .env
```

By default `INCIDENT_TRIAGE_BACKEND=mock` reads `tests/fixtures/mock_incidents.csv`, so the
pipeline runs end-to-end without any Databricks workspace access — useful while waiting on
credentials. Set `ANTHROPIC_API_KEY` to exercise the real Claude call.

## Run

```
python scripts/run_digest.py            # print the digest
python scripts/run_digest.py --send      # also email it (needs SMTP_* in .env)
```

## Test

```
pytest
```

Tests cover dedup and schema only — no network calls. The Claude call (P4) and the real
Databricks read are exercised manually via `run_digest.py`, not in the test suite.

## Switching to the real Databricks table

```
INCIDENT_TRIAGE_BACKEND=databricks
DATABRICKS_SERVER_HOSTNAME=...
DATABRICKS_HTTP_PATH=...
DATABRICKS_TOKEN=...
```

Requires `pip install -e ".[databricks]"`.
