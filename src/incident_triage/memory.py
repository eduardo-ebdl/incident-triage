"""P8 - synthetic resolution memory and Databricks AI Search retrieval."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

DEFAULT_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "resolution_memory.json"
SEARCH_COLUMNS = [
    "resolution_id",
    "error_type",
    "category",
    "error_pattern",
    "resolution",
    "source",
    "confirmed",
]


class ResolutionRecord(BaseModel):
    resolution_id: str
    error_type: str
    category: str
    error_pattern: str
    resolution: str
    source: str
    confirmed: bool = True

    @property
    def search_text(self) -> str:
        return (
            f"Error type: {self.error_type}\n"
            f"Category: {self.category}\n"
            f"Pattern: {self.error_pattern}\n"
            f"Resolution: {self.resolution}"
        )


class ResolutionMatch(ResolutionRecord):
    score: float = Field(ge=0.0)


class SearchIndex(Protocol):
    def similarity_search(self, **kwargs: Any) -> dict[str, Any]: ...


def load_resolution_seed(path: Path = DEFAULT_SEED_PATH) -> list[ResolutionRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = [ResolutionRecord.model_validate(item) for item in payload]
    ids = [record.resolution_id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("resolution seed contains duplicate resolution_id values")
    return records


def search_past_resolutions(
    query_text: str,
    *,
    num_results: int = 5,
    index: SearchIndex | None = None,
) -> list[ResolutionMatch]:
    if not query_text.strip():
        raise ValueError("query_text must not be empty")
    if num_results < 1:
        raise ValueError("num_results must be at least 1")

    index = index or _configured_index()
    response = index.similarity_search(
        query_text=query_text,
        columns=SEARCH_COLUMNS,
        num_results=num_results,
        query_type="HYBRID",
    )
    return _parse_search_response(response)


def _configured_index() -> SearchIndex:
    try:
        from databricks.ai_search.client import AISearchClient
    except ImportError as exc:
        raise RuntimeError(
            'Databricks AI Search support is not installed; use pip install -e ".[rag]"'
        ) from exc

    workspace_url = os.environ["DATABRICKS_SERVER_HOSTNAME"]
    if not workspace_url.startswith(("http://", "https://")):
        workspace_url = f"https://{workspace_url}"

    client = AISearchClient(
        workspace_url=workspace_url,
        personal_access_token=os.environ["DATABRICKS_TOKEN"],
    )
    index_name = os.environ["DATABRICKS_AI_SEARCH_INDEX"]
    endpoint_name = os.environ.get("DATABRICKS_AI_SEARCH_ENDPOINT")
    return client.get_index(endpoint_name=endpoint_name, index_name=index_name)


def _parse_search_response(response: dict[str, Any]) -> list[ResolutionMatch]:
    columns = [column["name"] for column in response["manifest"]["columns"]]
    matches: list[ResolutionMatch] = []

    for values in response.get("result", {}).get("data_array", []):
        row = dict(zip(columns, values))
        score = float(row.pop("score"))
        matches.append(ResolutionMatch(score=score, **row))

    return matches
