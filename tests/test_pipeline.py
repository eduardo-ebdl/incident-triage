import pytest

from incident_triage.dedup import IncidentGroup
from incident_triage.incidents import fetch_incidents
from incident_triage.pipeline import (
    _append_delivery_warning,
    _triage_unavailable,
    run_digest,
)
from incident_triage.schema import Category, RecommendedAction


def test_triage_unavailable_marks_incident_for_manual_review():
    group = IncidentGroup(representative=fetch_incidents(backend="mock")[0], occurrences=2)

    triage = _triage_unavailable(group, RuntimeError("api down"))

    assert triage.category is Category.UNKNOWN
    assert triage.recommended_action is RecommendedAction.ESCALATE
    assert triage.confidence == 0.0
    assert "RuntimeError" in triage.root_cause
    assert "ZeroDivisionError" in triage.root_cause


def test_run_digest_can_continue_when_one_llm_call_fails(monkeypatch):
    monkeypatch.setenv("INCIDENT_TRIAGE_BACKEND", "mock")
    calls = 0

    def fake_triage(group):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("api down")
        return _triage_unavailable(group, RuntimeError("stubbed"))

    monkeypatch.setattr("incident_triage.pipeline.triage_incident", fake_triage)

    body = run_digest()

    assert "Triage unavailable" in body
    assert "Incident digest" in body


def test_run_digest_can_fail_fast_on_llm_error(monkeypatch):
    monkeypatch.setenv("INCIDENT_TRIAGE_BACKEND", "mock")

    def fake_triage(_group):
        raise RuntimeError("api down")

    monkeypatch.setattr("incident_triage.pipeline.triage_incident", fake_triage)

    with pytest.raises(RuntimeError, match="api down"):
        run_digest(continue_on_triage_error=False)


def test_append_delivery_warning_keeps_digest_body_visible():
    body = _append_delivery_warning("digest body", TimeoutError("smtp down"))

    assert "digest body" in body
    assert "Digest email was not sent: TimeoutError" in body
