"""Orchestrator — wires P1 through P7 into a single run of the Stage 1 digest."""

from __future__ import annotations

from .aggregate import aggregate_by_job
from .dedup import dedup_incidents
from .digest import format_digest_text, send_digest_email
from .incidents import fetch_incidents
from .schema import TriageResult
from .triage import derive_transient_vs_real, triage_incident


def run_digest(send_email: bool = False, window: str = "1 day") -> str:
    rows = fetch_incidents(window=window)
    groups = dedup_incidents(rows)

    results: list[TriageResult] = []
    for group in groups:
        row = group.representative
        llm_triage = triage_incident(group)
        results.append(
            TriageResult(
                incident_id=row.incident_id,
                job_id=row.job_id,
                job_name=row.job_name,
                run_id=row.run_id,
                task_key=row.task_key,
                result_state=row.result_state,
                transient_vs_real=derive_transient_vs_real(row.result_state),
                occurrences=group.occurrences,
                **llm_triage.model_dump(),
            )
        )

    job_digests = aggregate_by_job(results)
    body = format_digest_text(job_digests)

    if send_email:
        send_digest_email(body)

    return body


if __name__ == "__main__":
    print(run_digest(send_email=False))
