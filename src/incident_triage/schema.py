"""Pydantic contracts for the Stage 1 digest pipeline (P2)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendedAction(str, Enum):
    RETRY = "retry"
    FIX = "fix"
    ESCALATE = "escalate"


class Category(str, Enum):
    TRANSIENT = "transient"
    CONFIG = "config"
    DATA = "data"
    CODE = "code"
    DEPENDENCY = "dependency"
    PERMISSION = "permission"
    RESOURCE = "resource"


class LLMTriage(BaseModel):
    """What the model actually produces — the tool-call output of P4."""

    category: Category
    severity: Severity
    root_cause: str = Field(description="1-2 sentence root cause, plain language")
    recommended_action: RecommendedAction
    confidence: float = Field(ge=0.0, le=1.0)


class TriageResult(BaseModel):
    """Full record: derived fields (from result_state/ids) + the LLM's judgment."""

    incident_id: str
    job_id: int
    job_name: str
    run_id: int
    task_key: str | None
    result_state: str
    transient_vs_real: str  # "transient" | "real" | "evaluate" — derived, not from the LLM
    occurrences: int = 1  # how many rows in today's window collapsed into this one (P3 dedup)

    category: Category
    severity: Severity
    root_cause: str
    recommended_action: RecommendedAction
    confidence: float = Field(ge=0.0, le=1.0)
