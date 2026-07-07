"""P3 — simple dedup: group same-day incidents by a hash of error_message.

Not semantic (that's the Estágio 2 embeddings fingerprint) — just enough so the
digest doesn't repeat the same error 10 times if it fired 10 times today.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .incidents import IncidentRow


def error_hash(error_message: str) -> str:
    normalized = error_message.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


@dataclass
class IncidentGroup:
    """One or more IncidentRows that share the same error_message."""

    representative: IncidentRow
    occurrences: int = 1
    all_rows: list[IncidentRow] = field(default_factory=list)


def dedup_incidents(rows: list[IncidentRow]) -> list[IncidentGroup]:
    groups: dict[str, IncidentGroup] = {}
    for row in rows:
        key = error_hash(row.error_message)
        if key not in groups:
            groups[key] = IncidentGroup(representative=row, occurrences=0, all_rows=[])
        groups[key].occurrences += 1
        groups[key].all_rows.append(row)
    return list(groups.values())
