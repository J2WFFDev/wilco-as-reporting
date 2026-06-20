"""Command-line interface for SASP data acquisition and discovery."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from wilco_as_reporting.api.sasp_client import SaspApiError, SaspClient
from wilco_as_reporting.discovery import discover_matches
from wilco_as_reporting.nationals_ops import NationalsOpsError
from wilco_as_reporting.parsers import MatchParseError, parse_match
from wilco_as_reporting.pipeline import (
    build_nationals_match,
    build_single_match,
    build_team_match,
)
from wilco_as_reporting.reports import (
    MatchReportError,
    TeamReportError,
    build_match_report,
    build_team_report,
)
from wilco_as_reporting.team_profiles import (
    TeamProfileError,
    load_team_profile,
)
from wilco_as_reporting.validators import (
    MatchValidationError,
    validate_match,
)
from wilco_as_reporting.workbooks import (
    MatchWorkbookError,
    NationalsWorkbookError,
    TeamWorkbookError,
    build_match_workbook,
    build_team_workbook,
)


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


def build_validate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli validate",
        description="Validate parsed SASP match score tables.",
    )
    parser.add_argument("--match-id", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def build_report_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli report",
        description="Build report-ready SASP match CSV tables.",
    )
    parser.add_argument("--match-id", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def build_workbook_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli workbook",
        description="Build an Excel workbook from report-ready tables.",
    )
    parser.add_argument("--match-id", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def build_pipeline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli build",
        description="Build a complete single-match report artifact.",
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


def build_team_report_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli team-report",
        description="Build coach-focused team report tables.",
    )
    parser.add_argument("--match-id", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--team-key", required=True)
    return parser


def build_team_workbook_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli team-workbook",
        description="Build a coach-focused team workbook.",
    )
    parser.add_argument("--match-id", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--team-key", required=True)
    return parser


def build_team_pipeline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli build-team",
        description="Build full-match and team coaching artifacts.",
    )
    parser.add_argument("--match-id", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--team-key", required=True)
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


def build_nationals_pipeline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli build-nationals",
        description=(
            "Refresh, snapshot, compare, and brief a monitored match."
        ),
    )
    parser.add_argument("--match-id", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--team-key", required=True)
    parser.add_argument(
        "--snapshot-label",
        default="manual",
        help="Short snapshot label such as morning, evening, or final.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace current raw snapshot files before preserving a copy.",
    )
    parser.add_argument(
        "--include-schedule",
        action="store_true",
        help="Fetch and save the match schedule snapshot.",
    )
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


def run_validate(arguments: Sequence[str]) -> int:
    args = build_validate_parser().parse_args(arguments)
    try:
        result = validate_match(
            match_id=args.match_id,
            output_dir=args.output_dir,
        )
    except MatchValidationError as exc:
        print(f"Error: {exc}")
        return 1

    print(f"validation summary rows: {result.summary_rows}")
    print(f"validation finding rows: {result.finding_rows}")
    print(
        "match reconciliation rows: "
        f"{result.match_reconciliation_rows}"
    )
    print(
        "stage reconciliation rows: "
        f"{result.stage_reconciliation_rows}"
    )
    print(
        "squad reconciliation rows: "
        f"{result.squad_reconciliation_rows}"
    )
    for severity in ("ERROR", "WARNING", "REVIEW", "INFO"):
        print(
            f"{severity} findings: "
            f"{result.severity_counts.get(severity, 0)}"
        )
    print(f"validation directory: {result.validation_summary_path.parent}")
    return 0


def run_report(arguments: Sequence[str]) -> int:
    args = build_report_parser().parse_args(arguments)
    try:
        result = build_match_report(
            match_id=args.match_id,
            output_dir=args.output_dir,
        )
    except MatchReportError as exc:
        print(f"Error: {exc}")
        return 1

    for filename, row_count in result.row_counts.items():
        print(f"{filename}: {row_count} rows")
    print(f"report tables directory: {result.team_summary_path.parent}")
    return 0


def run_workbook(arguments: Sequence[str]) -> int:
    args = build_workbook_parser().parse_args(arguments)
    try:
        result = build_match_workbook(
            match_id=args.match_id,
            output_dir=args.output_dir,
        )
    except MatchWorkbookError as exc:
        print(f"Error: {exc}")
        return 1

    print(f"workbook: {result.path}")
    print(f"workbook sheets: {', '.join(result.sheet_names)}")
    return 0


def run_build(arguments: Sequence[str]) -> int:
    args = build_pipeline_parser().parse_args(arguments)
    try:
        result = build_single_match(
            match_id=args.match_id,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            include_schedule=args.include_schedule,
        )
    except (
        SaspApiError,
        MatchParseError,
        MatchValidationError,
        MatchReportError,
        MatchWorkbookError,
    ) as exc:
        print(f"Error: {exc}")
        return 1

    raw_results = [
        result.snapshots.slots,
        result.snapshots.leaderboard,
    ]
    if result.snapshots.schedule is not None:
        raw_results.append(result.snapshots.schedule)
    print("raw files:")
    for snapshot in raw_results:
        print(f"  {snapshot.path} ({snapshot.status})")
    print("parsed rows:")
    print(f"  match_scores.csv: {result.parse_result.match_score_rows}")
    print(f"  rankings.csv: {result.parse_result.ranking_rows}")
    print(f"  squad_results.csv: {result.parse_result.squad_result_rows}")
    print(f"  stage_scores.csv: {result.parse_result.stage_score_rows}")
    print("validation findings:")
    for severity in ("ERROR", "WARNING", "REVIEW", "INFO"):
        count = result.validation_result.severity_counts.get(severity, 0)
        print(f"  {severity}: {count}")
    print("report rows:")
    for filename, row_count in result.report_result.row_counts.items():
        print(f"  {filename}: {row_count}")
    print(f"workbook: {result.workbook_result.path}")
    return 0


def run_team_report(arguments: Sequence[str]) -> int:
    args = build_team_report_parser().parse_args(arguments)
    try:
        profile = load_team_profile(args.team_key)
        result = build_team_report(
            match_id=args.match_id,
            output_dir=args.output_dir,
            profile=profile,
        )
    except (TeamProfileError, TeamReportError) as exc:
        print(f"Error: {exc}")
        return 1
    for filename, row_count in result.row_counts.items():
        print(f"{filename}: {row_count} rows")
    for limitation in result.limitations:
        print(f"Note: {limitation}")
    print(f"team report directory: {result.team_summary_path.parent}")
    return 0


def run_team_workbook(arguments: Sequence[str]) -> int:
    args = build_team_workbook_parser().parse_args(arguments)
    try:
        profile = load_team_profile(args.team_key)
        result = build_team_workbook(
            match_id=args.match_id,
            output_dir=args.output_dir,
            profile=profile,
        )
    except (TeamProfileError, TeamWorkbookError) as exc:
        print(f"Error: {exc}")
        return 1
    print(f"team workbook: {result.path}")
    print(f"team workbook sheets: {', '.join(result.sheet_names)}")
    return 0


def run_build_team(arguments: Sequence[str]) -> int:
    args = build_team_pipeline_parser().parse_args(arguments)
    try:
        profile = load_team_profile(args.team_key)
        result = build_team_match(
            match_id=args.match_id,
            output_dir=args.output_dir,
            profile=profile,
            overwrite=args.overwrite,
            include_schedule=args.include_schedule,
        )
    except (
        SaspApiError,
        MatchParseError,
        MatchValidationError,
        MatchReportError,
        MatchWorkbookError,
        TeamProfileError,
        TeamReportError,
        TeamWorkbookError,
    ) as exc:
        print(f"Error: {exc}")
        return 1

    full = result.full_build
    print(f"match_id: {args.match_id}")
    print(f"team_key: {profile.team_key}")
    print("raw files:")
    raw_results = [
        full.snapshots.slots,
        full.snapshots.leaderboard,
    ]
    if full.snapshots.schedule is not None:
        raw_results.append(full.snapshots.schedule)
    for snapshot in raw_results:
        print(f"  {snapshot.path} ({snapshot.status})")
    print("parsed rows:")
    print(f"  match_scores.csv: {full.parse_result.match_score_rows}")
    print(f"  rankings.csv: {full.parse_result.ranking_rows}")
    print(
        "  squad_results.csv: "
        f"{full.parse_result.squad_result_rows}"
    )
    print(f"  stage_scores.csv: {full.parse_result.stage_score_rows}")
    print("validation findings:")
    for severity in ("ERROR", "WARNING", "REVIEW", "INFO"):
        count = full.validation_result.severity_counts.get(
            severity,
            0,
        )
        print(f"  {severity}: {count}")
    print("full report rows:")
    for filename, row_count in full.report_result.row_counts.items():
        print(f"  {filename}: {row_count}")
    print("team report rows:")
    for filename, row_count in (
        result.team_report_result.row_counts.items()
    ):
        print(f"  {filename}: {row_count}")
    for limitation in result.team_report_result.limitations:
        print(f"team report note: {limitation}")
    print(f"full workbook: {full.workbook_result.path}")
    print(f"team workbook: {result.team_workbook_result.path}")
    return 0


def run_build_nationals(arguments: Sequence[str]) -> int:
    args = build_nationals_pipeline_parser().parse_args(arguments)
    try:
        profile = load_team_profile(args.team_key)
        result = build_nationals_match(
            match_id=args.match_id,
            output_dir=args.output_dir,
            profile=profile,
            snapshot_label=args.snapshot_label,
            overwrite=args.overwrite,
            include_schedule=args.include_schedule,
        )
    except (
        SaspApiError,
        MatchParseError,
        MatchValidationError,
        MatchReportError,
        MatchWorkbookError,
        TeamProfileError,
        TeamReportError,
        TeamWorkbookError,
        NationalsOpsError,
        NationalsWorkbookError,
    ) as exc:
        print(f"Error: {exc}")
        return 1

    operations = result.operations_result
    print(f"match_id: {args.match_id}")
    print(f"team_key: {profile.team_key}")
    print(f"snapshot path: {operations.snapshot_path}")
    print(
        "previous snapshot: "
        + (
            str(operations.previous_snapshot_path)
            if operations.previous_snapshot_path
            else "BASELINE"
        )
    )
    print(f"comparison status: {operations.comparison_status}")
    print(f"data status: {operations.data_status}")
    print("validation findings:")
    for severity in ("ERROR", "WARNING", "REVIEW"):
        print(
            f"  {severity}: "
            f"{operations.validation_counts.get(severity, 0)}"
        )
    print(
        f"changed athlete count: "
        f"{operations.changed_athlete_count}"
    )
    print(f"changed award count: {operations.changed_award_count}")
    print(f"changed squad count: {operations.changed_squad_count}")
    print(f"new review count: {operations.new_review_count}")
    print(f"operations workbook: {operations.workbook_path}")
    for note in operations.notes:
        print(f"operations note: {note}")
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
    if command_arguments and command_arguments[0] == "validate":
        return run_validate(command_arguments[1:])
    if command_arguments and command_arguments[0] == "report":
        return run_report(command_arguments[1:])
    if command_arguments and command_arguments[0] == "workbook":
        return run_workbook(command_arguments[1:])
    if command_arguments and command_arguments[0] == "build":
        return run_build(command_arguments[1:])
    if command_arguments and command_arguments[0] == "team-report":
        return run_team_report(command_arguments[1:])
    if command_arguments and command_arguments[0] == "team-workbook":
        return run_team_workbook(command_arguments[1:])
    if command_arguments and command_arguments[0] == "build-team":
        return run_build_team(command_arguments[1:])
    if command_arguments and command_arguments[0] == "build-nationals":
        return run_build_nationals(command_arguments[1:])
    return run_fetch(command_arguments)


if __name__ == "__main__":
    raise SystemExit(main())
