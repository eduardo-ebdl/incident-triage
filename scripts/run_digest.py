#!/usr/bin/env python
"""Entry point: run the Stage 1 digest pipeline end to end.

Usage:
    python scripts/run_digest.py                    # print digest, don't send email
    python scripts/run_digest.py --send              # also send over SMTP
    python scripts/run_digest.py --window "90 day"   # widen the lookback window
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv  # noqa: E402

from incident_triage.pipeline import run_digest  # noqa: E402


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="actually send the email")
    parser.add_argument(
        "--window", default="1 day", help="lookback window, e.g. '1 day', '90 day'"
    )
    args = parser.parse_args()

    body = run_digest(send_email=args.send, window=args.window)
    print(body)


if __name__ == "__main__":
    main()
