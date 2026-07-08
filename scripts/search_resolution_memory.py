"""Query the Stage 2 resolution memory in Databricks AI Search."""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from incident_triage.memory import search_past_resolutions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Error message or trace fragment to search for")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    load_dotenv()
    matches = search_past_resolutions(args.query, num_results=args.limit)
    for position, match in enumerate(matches, start=1):
        print(
            f"{position}. [{match.score:.3f}] {match.error_type} - {match.source}\n"
            f"   {match.resolution}"
        )


if __name__ == "__main__":
    main()
