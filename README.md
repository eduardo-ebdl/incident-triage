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
- Retrieves up to three similar synthetic resolutions and includes a suggested fix only when
  Claude finds a genuine match, citing the resolution identifiers used.
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

Stage 2 has started: a synthetic resolution-memory corpus, a Databricks AI Search provisioner,
and single-shot retrieval-augmented triage wired into the Claude call — each incident's error
message is used to retrieve up to 3 past resolutions, and the model only cites a fix when one
genuinely applies. See [docs/stage-2.md](docs/stage-2.md) for the exact status; the LangGraph
agent (P9), retrieval reranking (P10), and a code-level grounding guardrail (P11) are not
implemented yet — today "don't force a match" is a prompt instruction, not an enforced check.

The intermediate Stage 1.5 work is also complete: portfolio documentation, a sanitized digest,
a manual evaluation checklist, per-incident LLM fallback, and SMTP failure handling.

## Data contract

Table: `observability.dev.job_error_logs` (owned and populated by the DE side).

Important columns consumed by this repo:

- `job_id`, `job_name`, `run_id`, `run_name`, `task_key`
- `result_state`, `state_message`
- `error_message`, `error_trace`
- `run_page_url`
- `log_timestamp`, `start_time`, `end_time`, `duration_seconds`, `trigger`
- P9 preparation columns: `task_run_id`, `attempt_number`, `repair_history`, `libraries`,
  `cluster_spec`, `spark_version`, `num_workers`, `spark_conf`

The P9 preparation columns already exist in Delta, but the current `IncidentRow` and P1 query do
not consume them yet. `task_run_id` and `attempt_number` are populated for newer rows;
`repair_history` is still an ingestion gap, while cluster fields are expected to stay null for
the synthetic serverless jobs.

## Architecture

```text
src/incident_triage/
  incidents.py   read incidents from mock CSV or Databricks SQL
  schema.py      Pydantic schemas for structured triage
  dedup.py       group repeated errors by message hash
  memory.py      query the synthetic resolution memory through Databricks AI Search
  triage.py      retrieve context + Claude tool-call triage + optional MLflow tracing
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

The 16 local tests cover deduplication, schemas, memory response parsing, retrieval degradation,
and pipeline fallback behavior. They avoid network calls and do not require API keys. Real Claude,
Databricks SQL, and AI Search checkpoints are exercised manually.

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

Near-term work is focused on P9 and evidence for the portfolio:

- Keep the sanitized sample digest in [docs/sample_digest.md](docs/sample_digest.md) aligned
  with the current output format.
- Use [docs/evaluation.md](docs/evaluation.md) as the manual evaluation checklist for
  expected vs. model-produced classifications.
- Document how to inspect MLflow traces and which run metadata matters.
- Add the LangGraph investigation flow without depending on serverless cluster metadata that is
  unavailable for these synthetic jobs.

Stage 2 should add retrieval only when it has useful context to retrieve, such as synthetic
runbooks, known exception patterns, historical incident notes, or Databricks troubleshooting
docs. LangGraph or a multi-step agent flow should earn its place through a real workflow:
classify, retrieve context, decide action, and produce the digest.
