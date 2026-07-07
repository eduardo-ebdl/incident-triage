"""P4 — one Claude call per incident group, forced into the LLMTriage tool schema.

P7 — MLflow tracing wraps the call: @mlflow.trace when mlflow is installed and
configured, no-op otherwise (keeps local dev without a tracking server unblocked).
"""

from __future__ import annotations

import json
import os

from .dedup import IncidentGroup
from .schema import Category, LLMTriage, RecommendedAction, Severity

MODEL_DEV = "claude-haiku-4-5"
MODEL_PROD = "claude-sonnet-4-6"

TRIAGE_TOOL = {
    "name": "submit_triage",
    "description": "Submit the triage judgment for this Databricks job failure.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": [c.value for c in Category]},
            "severity": {"type": "string", "enum": [s.value for s in Severity]},
            "root_cause": {
                "type": "string",
                "description": "1-2 sentence root cause in plain language, e.g. "
                "'OOM on driver during a large join'.",
            },
            "recommended_action": {
                "type": "string",
                "enum": [a.value for a in RecommendedAction],
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": ["category", "severity", "root_cause", "recommended_action", "confidence"],
    },
}

SYSTEM_PROMPT = (
    "You are triaging a failed Databricks job run for an on-call data engineer. "
    "You get the error message, the stack trace, and the run's result_state. "
    "Judge severity and category from evidence in the trace only — do not invent causes "
    "not supported by the text. Call submit_triage with your judgment."
)


def _user_prompt(group: IncidentGroup) -> str:
    row = group.representative
    occurrence_note = (
        f"\n\n(This exact error occurred {group.occurrences} times in today's window.)"
        if group.occurrences > 1
        else ""
    )
    return (
        f"job_name: {row.job_name}\n"
        f"task_key: {row.task_key}\n"
        f"result_state: {row.result_state}\n"
        f"state_message: {row.state_message}\n"
        f"error_message: {row.error_message}\n"
        f"error_trace:\n{row.error_trace}"
        f"{occurrence_note}"
    )


def _maybe_trace(fn):
    try:
        import mlflow

        return mlflow.trace(fn)
    except ImportError:
        return fn


@_maybe_trace
def triage_incident(group: IncidentGroup, model: str | None = None) -> LLMTriage:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = model or os.environ.get("INCIDENT_TRIAGE_MODEL", MODEL_DEV)

    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        tools=[TRIAGE_TOOL],
        tool_choice={"type": "tool", "name": "submit_triage"},
        messages=[{"role": "user", "content": _user_prompt(group)}],
    )

    tool_use = next(block for block in response.content if block.type == "tool_use")
    return LLMTriage.model_validate(tool_use.input)


def derive_transient_vs_real(result_state: str) -> str:
    """result_state -> transient_vs_real, per the spec (not the LLM's call)."""
    if result_state == "FAILED":
        return "real"
    if result_state == "TIMEDOUT":
        return "evaluate"
    return "evaluate"
