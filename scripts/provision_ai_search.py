"""Seed the resolution memory and provision the Stage 2 Databricks AI Search index."""

from __future__ import annotations

import argparse
import os
import re

from dotenv import load_dotenv

from incident_triage.memory import ResolutionRecord, load_resolution_seed

DEFAULT_TABLE = "observability.dev.resolution_memory"
DEFAULT_INDEX = "observability.dev.resolution_memory_index"
DEFAULT_ENDPOINT = "incident-triage-ai-search"
DEFAULT_EMBEDDING_ENDPOINT = "databricks-qwen3-embedding-0-6b"
_UC_NAME_RE = re.compile(r"^[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Create/update the Delta table without provisioning AI Search.",
    )
    return parser.parse_args()


def _configured_name(env_name: str, default: str) -> str:
    value = os.environ.get(env_name, default)
    if env_name in {"DATABRICKS_RESOLUTION_TABLE", "DATABRICKS_AI_SEARCH_INDEX"}:
        if not _UC_NAME_RE.fullmatch(value):
            raise ValueError(f"{env_name} must be a three-part Unity Catalog name")
    return value


def _seed_table(table_name: str, records: list[ResolutionRecord]) -> None:
    from databricks import sql

    create_table = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            resolution_id STRING NOT NULL,
            error_type STRING NOT NULL,
            category STRING NOT NULL,
            error_pattern STRING NOT NULL,
            resolution STRING NOT NULL,
            source STRING NOT NULL,
            search_text STRING NOT NULL,
            confirmed BOOLEAN NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        USING DELTA
        TBLPROPERTIES (delta.enableChangeDataFeed = true)
    """
    merge_record = f"""
        MERGE INTO {table_name} AS target
        USING (
            SELECT
                ? AS resolution_id,
                ? AS error_type,
                ? AS category,
                ? AS error_pattern,
                ? AS resolution,
                ? AS source,
                ? AS search_text,
                ? AS confirmed
        ) AS source
        ON target.resolution_id = source.resolution_id
        WHEN MATCHED THEN UPDATE SET
            target.error_type = source.error_type,
            target.category = source.category,
            target.error_pattern = source.error_pattern,
            target.resolution = source.resolution,
            target.source = source.source,
            target.search_text = source.search_text,
            target.confirmed = source.confirmed,
            target.updated_at = current_timestamp()
        WHEN NOT MATCHED THEN INSERT (
            resolution_id, error_type, category, error_pattern, resolution,
            source, search_text, confirmed, updated_at
        ) VALUES (
            source.resolution_id, source.error_type, source.category, source.error_pattern,
            source.resolution, source.source, source.search_text, source.confirmed,
            current_timestamp()
        )
    """

    with sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(create_table)
            for record in records:
                cursor.execute(
                    merge_record,
                    (
                        record.resolution_id,
                        record.error_type,
                        record.category,
                        record.error_pattern,
                        record.resolution,
                        record.source,
                        record.search_text,
                        record.confirmed,
                    ),
                )


def _provision_index(
    *,
    table_name: str,
    index_name: str,
    endpoint_name: str,
    embedding_endpoint: str,
) -> None:
    from databricks.ai_search.client import AISearchClient

    workspace_url = os.environ["DATABRICKS_SERVER_HOSTNAME"]
    if not workspace_url.startswith(("http://", "https://")):
        workspace_url = f"https://{workspace_url}"

    client = AISearchClient(
        workspace_url=workspace_url,
        personal_access_token=os.environ["DATABRICKS_TOKEN"],
    )
    if not client.endpoint_exists(endpoint_name):
        client.create_endpoint_and_wait(name=endpoint_name, endpoint_type="STANDARD")

    if client.index_exists(endpoint_name=endpoint_name, index_name=index_name):
        index = client.get_index(endpoint_name=endpoint_name, index_name=index_name)
        index.wait_until_ready()
        index.sync()
        index.wait_until_ready()
        return

    index = client.create_delta_sync_index(
        endpoint_name=endpoint_name,
        source_table_name=table_name,
        index_name=index_name,
        pipeline_type="TRIGGERED",
        primary_key="resolution_id",
        embedding_source_column="search_text",
        embedding_model_endpoint_name=embedding_endpoint,
        columns_to_sync=[
            "error_type",
            "category",
            "error_pattern",
            "resolution",
            "source",
            "confirmed",
        ],
    )
    index.wait_until_ready()


def main() -> None:
    load_dotenv()
    args = _parse_args()
    records = load_resolution_seed()

    table_name = _configured_name("DATABRICKS_RESOLUTION_TABLE", DEFAULT_TABLE)
    index_name = _configured_name("DATABRICKS_AI_SEARCH_INDEX", DEFAULT_INDEX)
    endpoint_name = _configured_name("DATABRICKS_AI_SEARCH_ENDPOINT", DEFAULT_ENDPOINT)
    embedding_endpoint = _configured_name(
        "DATABRICKS_EMBEDDING_ENDPOINT", DEFAULT_EMBEDDING_ENDPOINT
    )

    _seed_table(table_name, records)
    print(f"Seeded {len(records)} synthetic resolutions into {table_name}.")

    if not args.seed_only:
        _provision_index(
            table_name=table_name,
            index_name=index_name,
            endpoint_name=endpoint_name,
            embedding_endpoint=embedding_endpoint,
        )
        print(f"AI Search index provisioned: {index_name}")


if __name__ == "__main__":
    main()
