"""Command-line interface for fetching raw SASP match data."""

from __future__ import annotations

import argparse
from pathlib import Path

from wilco_as_reporting.api.sasp_client import SaspApiError, SaspClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch immutable raw SASP JSON snapshots for a match."
    )
    parser.add_argument("--match-id", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing raw snapshot files.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    client = SaspClient()

    try:
        snapshots = client.fetch_match_snapshots(
            match_id=args.match_id,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    except SaspApiError as exc:
        print(f"Error: {exc}")
        return 1

    print(f"match_id: {args.match_id}")
    print(
        f"slots file: {snapshots.slots.path} "
        f"({snapshots.slots.status})"
    )
    print(
        f"leaderboard file: {snapshots.leaderboard.path} "
        f"({snapshots.leaderboard.status})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

