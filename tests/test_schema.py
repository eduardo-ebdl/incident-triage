import pytest
from incident_triage.incidents import fetch_incidents
from incident_triage.schema import Category, RecommendedAction, Severity, TriageResult
from incident_triage.triage import derive_transient_vs_real


def test_derive_transient_vs_real_from_result_state():
    assert derive_transient_vs_real("FAILED") == "real"
    assert derive_transient_vs_real("TIMEDOUT") == "evaluate"


def test_triage_result_roundtrip():
    result = TriageResult(
        incident_id="90001-main_task",
        job_id=101,
        job_name="Error Test - ZeroDivisionError",
        run_id=90001,
        task_key="main_task",
        result_state="FAILED",
        transient_vs_real="real",
        occurrences=2,
        category=Category.CODE,
        severity=Severity.MEDIUM,
        root_cause="Division by zero in main_task.",
        recommended_action=RecommendedAction.FIX,
        confidence=0.9,
    )
    assert result.occurrences == 2
    assert result.category is Category.CODE


def test_triage_result_rejects_bad_confidence():
    with pytest.raises(ValueError):
        TriageResult(
            incident_id="x",
            job_id=1,
            job_name="j",
            run_id=1,
            task_key=None,
            result_state="FAILED",
            transient_vs_real="real",
            category=Category.CODE,
            severity=Severity.LOW,
            root_cause="x",
            recommended_action=RecommendedAction.RETRY,
            confidence=1.5,  # out of [0, 1]
        )


def test_fetch_incidents_mock_backend_reads_fixture():
    rows = fetch_incidents(backend="mock")
    assert len(rows) == 12
    assert all(r.result_state in ("FAILED", "TIMEDOUT") for r in rows)
