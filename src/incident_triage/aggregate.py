"""P5 — aggregate TriageResults by job and severity, recurrent vs new."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .schema import TriageResult


@dataclass
class JobDigest:
    job_id: int
    job_name: str
    results: list[TriageResult]

    @property
    def recurrent(self) -> list[TriageResult]:
        return [r for r in self.results if r.occurrences > 1]

    @property
    def new(self) -> list[TriageResult]:
        return [r for r in self.results if r.occurrences == 1]


def aggregate_by_job(results: list[TriageResult]) -> list[JobDigest]:
    by_job: dict[int, list[TriageResult]] = defaultdict(list)
    names: dict[int, str] = {}
    for r in results:
        by_job[r.job_id].append(r)
        names[r.job_id] = r.job_name

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    digests = [
        JobDigest(job_id=job_id, job_name=names[job_id], results=rows)
        for job_id, rows in by_job.items()
    ]
    digests.sort(
        key=lambda d: min(severity_rank.get(r.severity.value, 9) for r in d.results)
    )
    return digests
