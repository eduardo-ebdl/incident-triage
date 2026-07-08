from incident_triage.memory import load_resolution_seed, search_past_resolutions


def test_resolution_seed_is_valid_and_has_stage_two_scope():
    records = load_resolution_seed()

    assert 15 <= len(records) <= 20
    assert len({record.resolution_id for record in records}) == len(records)
    assert all(record.source.startswith("synthetic-runbook/") for record in records)
    assert all(record.search_text for record in records)


def test_search_past_resolutions_parses_ai_search_response():
    class FakeIndex:
        def similarity_search(self, **kwargs):
            assert kwargs["query_type"] == "HYBRID"
            return {
                "manifest": {
                    "columns": [
                        {"name": "resolution_id"},
                        {"name": "error_type"},
                        {"name": "category"},
                        {"name": "error_pattern"},
                        {"name": "resolution"},
                        {"name": "source"},
                        {"name": "confirmed"},
                        {"name": "score"},
                    ]
                },
                "result": {
                    "data_array": [
                        [
                            "res-spark-oom-001",
                            "OutOfMemoryError",
                            "resource",
                            "Spark stage failed with Java heap space.",
                            "Tune the join before adding memory.",
                            "synthetic-runbook/spark-join-oom",
                            True,
                            0.91,
                        ]
                    ]
                },
            }

    matches = search_past_resolutions("OutOfMemoryError during join", index=FakeIndex())

    assert len(matches) == 1
    assert matches[0].resolution_id == "res-spark-oom-001"
    assert matches[0].score == 0.91
