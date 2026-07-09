from incident_triage.memory import ResolutionMatch
from incident_triage.triage import _format_matches, _retrieve_grounding
from incident_triage.incidents import fetch_incidents


def test_format_matches_with_no_results():
    assert "none found" in _format_matches([])


def test_format_matches_includes_resolution_id_and_source():
    match = ResolutionMatch(
        resolution_id="res-spark-oom-001",
        error_type="OutOfMemoryError",
        category="resource",
        error_pattern="Spark stage failed with Java heap space.",
        resolution="Tune the join before adding memory.",
        source="synthetic-runbook/spark-join-oom",
        score=0.91,
    )

    text = _format_matches([match])

    assert "res-spark-oom-001" in text
    assert "synthetic-runbook/spark-join-oom" in text
    assert "Tune the join before adding memory." in text


def test_retrieve_grounding_degrades_to_empty_without_stage_two_config(monkeypatch):
    for var in (
        "DATABRICKS_AI_SEARCH_INDEX",
        "DATABRICKS_SERVER_HOSTNAME",
        "DATABRICKS_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)

    row = fetch_incidents(backend="mock")[0]

    assert _retrieve_grounding(row) == []
