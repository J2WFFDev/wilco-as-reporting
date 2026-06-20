"""Command-line interface for SASP data acquisition and discovery."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from wilco_as_reporting.api.sasp_client import SaspApiError, SaspClient
from wilco_as_reporting.discovery import discover_matches
from wilco_as_reporting.parsers import MatchParseError, parse_match


def build_fetch_parser() -> argparse.ArgumentParser:
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
    parser.add_argument(
        "--include-schedule",
        action="store_true",
        help="Fetch and save the match schedule snapshot.",
    )
    return parser


def build_discover_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli discover",
        description="Discover SASP competitions and build match indexes.",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--overrides",
        default=Path("config/match_overrides.csv"),
        type=Path,
        help="Curated match override CSV.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing raw discovery snapshots.",
    )
    return parser


def build_parse_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli parse",
        description="Parse raw SASP match snapshots into base CSV tables.",
    )
    parser.add_argument("--match-id", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def run_fetch(arguments: Sequence[str]) -> int:
    args = build_fetch_parser().parse_args(arguments)
    client = SaspClient()

    try:
        snapshots = client.fetch_match_snapshots(
            match_id=args.match_id,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            include_schedule=args.include_schedule,
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
    if snapshots.schedule is not None:
        print(
            f"schedule file: {snapshots.schedule.path} "
            f"({snapshots.schedule.status})"
        )
    return 0


def run_discover(arguments: Sequence[str]) -> int:
    args = build_discover_parser().parse_args(arguments)
    client = SaspClient()

    try:
        result = discover_matches(
            client,
            output_dir=args.output_dir,
            overrides_path=args.overrides,
            overwrite=args.overwrite,
        )
    except (SaspApiError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"pages processed: {result.pages_processed}")
    print(f"matches discovered: {result.matches_discovered}")
    print(f"matches included: {result.matches_included}")
    print(f"match index: {result.match_index_path}")
    print(f"effective match index: {result.effective_match_index_path}")
    return 0


def run_parse(arguments: Sequence[str]) -> int:
    args = build_parse_parser().parse_args(arguments)
    try:
        result = parse_match(
            match_id=args.match_id,
            output_dir=args.output_dir,
        )
    except MatchParseError as exc:
        print(f"Error: {exc}")
        return 1

    print(f"match score rows: {result.match_score_rows}")
    print(f"ranking rows: {result.ranking_rows}")
    print(f"squad result rows: {result.squad_result_rows}")
    print(f"stage score rows: {result.stage_score_rows}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    print(f"tables directory: {result.match_scores_path.parent}")
    return 0


def main(arguments: Sequence[str] | None = None) -> int:
    command_arguments = list(
        sys.argv[1:] if arguments is None else arguments
    )
    if command_arguments and command_arguments[0] == "discover":
        return run_discover(command_arguments[1:])
    if command_arguments and command_arguments[0] == "fetch":
        return run_fetch(command_arguments[1:])
    if command_arguments and command_arguments[0] == "parse":
        return run_parse(command_arguments[1:])
    return run_fetch(command_arguments)


if __name__ == "__main__":
    raise SystemExit(main())
