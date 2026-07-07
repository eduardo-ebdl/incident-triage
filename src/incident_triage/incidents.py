"""P1 — read the incidents seam: observability.dev.job_error_logs.

Two backends:
- "databricks": real table, via databricks-sql-connector.
- "mock": tests/fixtures/mock_incidents.csv, for local dev without workspace access.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

CATALOG = "observability"
SCHEMA = "dev"
TABLE = "job_error_logs"
FULL_TABLE_NAME = f"{CATALOG}.{SCHEMA}.{TABLE}"

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "mock_incidents.csv"


@dataclass
class IncidentRow:
    log_timestamp: str
    job_id: int
    job_name: str
    run_id: int
    run_name: str
    start_time: str
    end_time: str
    duration_seconds: int
    result_state: str
    state_message: str
    task_key: str
    error_message: str
    error_trace: str
    run_page_url: str
    trigger: str

    @property
    def incident_id(self) -> str:
        return f"{self.run_id}-{self.task_key}"


def fetch_incidents(window: str = "1 day", backend: str | None = None) -> list[IncidentRow]:
    """Fetch failed/timed-out runs from the last `window`.

    backend defaults to $INCIDENT_TRIAGE_BACKEND, falling back to "mock" if unset —
    the real workspace isn't reachable from every dev machine, so mock is the safe default.
    """
    backend = backend or os.environ.get("INCIDENT_TRIAGE_BACKEND", "mock")
    if backend == "mock":
        return _fetch_from_csv(FIXTURE_PATH)
    if backend == "databricks":
        return _fetch_from_databricks(window)
    raise ValueError(f"unknown backend: {backend}")


def _fetch_from_csv(path: Path) -> list[IncidentRow]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            IncidentRow(
                log_timestamp=row["log_timestamp"],
                job_id=int(row["job_id"]),
                job_name=row["job_name"],
                run_id=int(row["run_id"]),
                run_name=row["run_name"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                duration_seconds=int(row["duration_seconds"]),
                result_state=row["result_state"],
                state_message=row["state_message"],
                task_key=row["task_key"],
                error_message=row["error_message"],
                error_trace=row["error_trace"],
                run_page_url=row["run_page_url"],
                trigger=row["trigger"],
            )
            for row in reader
        ]


def _fetch_from_databricks(window: str) -> list[IncidentRow]:
    from databricks import sql  # imported lazily — only needed for this backend

    server_hostname = os.environ["DATABRICKS_SERVER_HOSTNAME"]
    http_path = os.environ["DATABRICKS_HTTP_PATH"]
    access_token = os.environ["DATABRICKS_TOKEN"]

    query = f"""
        SELECT log_timestamp, job_id, job_name, run_id, run_name, start_time, end_time,
               duration_seconds, result_state, state_message, task_key, error_message,
               error_trace, run_page_url, trigger
        FROM {FULL_TABLE_NAME}
        WHERE log_timestamp >= now() - INTERVAL {window}
          AND result_state IN ('FAILED', 'TIMEDOUT')
    """

    with sql.connect(
        server_hostname=server_hostname, http_path=http_path, access_token=access_token
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            columns = [c[0] for c in cursor.description]
            rows = cursor.fetchall()

    return [IncidentRow(**dict(zip(columns, row))) for row in rows]
