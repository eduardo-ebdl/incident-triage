from incident_triage.dedup import dedup_incidents, error_hash
from incident_triage.incidents import fetch_incidents


def test_error_hash_is_stable_and_case_insensitive():
    assert error_hash("KeyError: 'x'") == error_hash("keyerror: 'x'")
    assert error_hash("KeyError: 'x'") != error_hash("KeyError: 'y'")


def test_dedup_collapses_repeated_zero_division_error():
    rows = fetch_incidents(backend="mock")
    groups = dedup_incidents(rows)

    zero_div_groups = [
        g for g in groups if "ZeroDivisionError" in g.representative.error_message
    ]
    assert len(zero_div_groups) == 1
    assert zero_div_groups[0].occurrences == 2


def test_dedup_keeps_distinct_errors_separate():
    rows = fetch_incidents(backend="mock")
    groups = dedup_incidents(rows)

    # 11 distinct error_messages in the fixture (10 single-task types + 1 timeout),
    # collapsed from 12 rows because ZeroDivisionError repeats twice.
    assert len(groups) == 11
    assert sum(g.occurrences for g in groups) == len(rows)
