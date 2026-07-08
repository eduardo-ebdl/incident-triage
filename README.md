# Incident Triage Copilot — AI/ML side

Databricks job-failure triage copilot. This is a portfolio project built in a pair with a
Data Engineer: the DE side creates synthetic failing jobs and ingests failures into a Delta
table; this repo is the AI/ML side that reads those incidents, triages each distinct error
with Claude, and sends an actionable digest.

The goal is not to build a generic chatbot. The goal is a small operational copilot for an
on-call data engineer: reduce noisy job failures into grouped incidents, likely causes,
severity, and next actions.

Full architecture spec and execution plan live outside this repo, in the author's private
career-planning vault (not published here).

## What it does

- Reads failed and timed-out Databricks job runs from the incident table.
- Removes ANSI color codes from Python tracebacks before prompting or emailing.
- Deduplicates repeated failures by `error_message`, so the LLM is called once per distinct
  error pattern.
- Forces Claude to return a structured triage object with category, severity, root cause,
  recommended action, and confidence.
- Aggregates triage results by job and severity.
- Sends a plain-text SMTP digest suitable for a daily incident review.
- Wraps the LLM triage call with optional MLflow tracing.

## Status: Stage 1 complete

Stage 1 is an MVP digest pipeline:

```text
read incidents -> dedup -> Claude triage -> aggregate -> email digest -> trace LLM call
```

It has been verified end-to-end against the real Databricks table, not only the local mock.
During that validation, the pipeline surfaced a real issue in the ingestion job itself: a
`createDataFrame()` call without an explicit schema failed when one field was `None`, and the
same failure was written multiple times to the table.

No RAG or agent loop is included yet. That belongs to Stage 2, after the basic operational
workflow is demonstrable and reliable.

Stage 2 has started with the synthetic resolution-memory contract and Databricks AI Search
provisioner. See [docs/stage-2.md](docs/stage-2.md) for its exact status; the LangGraph agent
and grounding guardrail are not implemented yet.

## Data contract

Table: `observability.dev.job_error_logs` (owned and populated by the DE side).

Important columns consumed by this repo:

- `job_id`, `job_name`, `run_id`, `run_name`, `task_key`
- `result_state`, `state_message`
- `error_message`, `error_trace`
- `run_page_url`
- `log_timestamp`, `start_time`, `end_time`, `duration_seconds`, `trigger`

The current table does not include `task_run_id`; jobs are single-task, so `run_id` identifies
the execution for the current scope.

## Architecture

```text
src/incident_triage/
  incidents.py   read incidents from mock CSV or Databricks SQL
  schema.py      Pydantic schemas for structured triage
  dedup.py       group repeated errors by message hash
  triage.py      Claude tool-call triage + optional MLflow tracing
  aggregate.py   group triage results by job and severity
  digest.py      format and send the email digest
  pipeline.py    orchestrate the full Stage 1 flow
```

The mock backend reads `tests/fixtures/mock_incidents.csv`, so local development and tests do
not need Databricks credentials.

## Example output shape

```text
Incident Triage Digest

Job: synthetic-null-value-job
Severity: high
Occurrences: 3
Category: data
Root cause: The job failed while processing null values in a field that the downstream step
expected to be non-null.
Recommended action: fix
Confidence: 0.86
```

This is illustrative and sanitized; real credentials, workspace URLs, and private data are not
committed to the repo.

See [docs/sample_digest.md](docs/sample_digest.md) for a longer sanitized sample.

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env
```

By default `INCIDENT_TRIAGE_BACKEND=mock` reads `tests/fixtures/mock_incidents.csv`, so the
pipeline runs end-to-end without Databricks workspace access. Set `ANTHROPIC_API_KEY` to
exercise the real Claude call.

For the full local environment:

```bash
pip install -e ".[dev,databricks,tracing,rag]"
```

## Run

```bash
python scripts/run_digest.py              # print the digest
python scripts/run_digest.py --send        # also email it (needs SMTP_* in .env)
python scripts/run_digest.py --window "90 day"
```

The synthetic jobs were seeded once, so a wider window may be needed when validating against
the shared Databricks workspace.

## Test

```bash
pytest
```

Tests cover deduplication, schema behavior, and pipeline fallback behavior. They avoid network
calls and do not require API keys. The real Claude call and Databricks read are exercised
manually through `scripts/run_digest.py`.

## Switching to the real Databricks table

```bash
INCIDENT_TRIAGE_BACKEND=databricks
DATABRICKS_SERVER_HOSTNAME=...
DATABRICKS_HTTP_PATH=...
DATABRICKS_TOKEN=...
```

Requires:

```bash
pip install -e ".[databricks]"
```

## Roadmap

Near-term improvements are focused on making the project more demonstrable and robust:

- Keep the sanitized sample digest in [docs/sample_digest.md](docs/sample_digest.md) aligned
  with the current output format.
- Use [docs/evaluation.md](docs/evaluation.md) as the manual evaluation checklist for
  expected vs. model-produced classifications.
- Document how to inspect MLflow traces and which run metadata matters.
- Keep improving digest resilience when one LLM call or the SMTP send fails.

Stage 2 should add retrieval only when it has useful context to retrieve, such as synthetic
runbooks, known exception patterns, historical incident notes, or Databricks troubleshooting
docs. LangGraph or a multi-step agent flow should earn its place through a real workflow:
classify, retrieve context, decide action, and produce the digest.
