"""Orchestrator — wires P1 through P7 into a single run of the Stage 1 digest."""

from __future__ import annotations

from .aggregate import aggregate_by_job
from .dedup import IncidentGroup, dedup_incidents
from .digest import format_digest_text, send_digest_email
from .incidents import fetch_incidents
from .schema import Category, LLMTriage, RecommendedAction, Severity, TriageResult
from .triage import derive_transient_vs_real, triage_incident


def run_digest(
    send_email: bool = False, window: str = "1 day", continue_on_triage_error: bool = True
) -> str:
    rows = fetch_incidents(window=window)
    groups = dedup_incidents(rows)

    results: list[TriageResult] = []
    for group in groups:
        try:
            llm_triage = triage_incident(group)
        except Exception as exc:
            if not continue_on_triage_error:
                raise
            llm_triage = _triage_unavailable(group, exc)

        results.append(_build_triage_result(group, llm_triage))

    job_digests = aggregate_by_job(results)
    body = format_digest_text(job_digests)

    if send_email:
        try:
            send_digest_email(body)
        except Exception as exc:
            body = _append_delivery_warning(body, exc)

    return body


def _build_triage_result(group: IncidentGroup, llm_triage: LLMTriage) -> TriageResult:
    row = group.representative
    return TriageResult(
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


def _triage_unavailable(group: IncidentGroup, exc: Exception) -> LLMTriage:
    row = group.representative
    return LLMTriage(
        category=Category.UNKNOWN,
        severity=Severity.MEDIUM,
        root_cause=(
            f"Triage unavailable: {exc.__class__.__name__} while calling the LLM. "
            f"Review the raw error manually: {row.error_message}"
        ),
        recommended_action=RecommendedAction.ESCALATE,
        confidence=0.0,
    )


def _append_delivery_warning(body: str, exc: Exception) -> str:
    return (
        f"{body}\n\n"
        f"[warning] Digest email was not sent: {exc.__class__.__name__}. "
        "The digest body was still generated."
    )


if __name__ == "__main__":
    print(run_digest(send_email=False))
