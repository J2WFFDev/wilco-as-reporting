"""Command-line interface for SASP data acquisition and discovery."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from wilco_as_reporting.api.sasp_client import SaspApiError, SaspClient
from wilco_as_reporting.batch_refresh import (
    BUILD_LEVELS,
    BatchRefreshError,
    run_backfill,
    run_incremental_refresh,
)
from wilco_as_reporting.discovery import discover_matches
from wilco_as_reporting.history import HistoryBuildError, build_history
from wilco_as_reporting.history_insights import (
    HistoryInsightsError,
    build_history_insights,
)
from wilco_as_reporting.nationals_ops import NationalsOpsError
from wilco_as_reporting.nationals_readiness import (
    NationalsReadinessError,
    build_nationals_readiness,
)
from wilco_as_reporting.parsers import MatchParseError, parse_match
from wilco_as_reporting.pipeline import (
    build_nationals_match,
    build_single_match,
    build_team_match,
)
from wilco_as_reporting.raw_downloader import (
    RawDownloadError,
    download_raw_matches,
)
from wilco_as_reporting.raw_inventory import (
    RawInventoryError,
    build_raw_inventory,
)
from wilco_as_reporting.records import RecordsBuildError, build_records
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


def build_backfill_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli backfill",
        description="Plan or run a bounded historical match backfill.",
    )
    parser.add_argument("--match-ids", default="")
    parser.add_argument("--from-date", type=date.fromisoformat)
    parser.add_argument("--to-date", type=date.fromisoformat)
    parser.add_argument("--post-types", default="")
    parser.add_argument("--team-key", default="wilco")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--include-schedule", action="store_true")
    parser.add_argument("--max-matches", default=10, type=int)
    parser.add_argument(
        "--build-level",
        choices=BUILD_LEVELS,
        default="validate",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--skip-unchanged",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--allow-over-max",
        action="store_true",
        help="Explicitly permit a selection larger than max-matches.",
    )
    return parser


def build_incremental_refresh_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli incremental-refresh",
        description="Plan or run watched, active, and recent refreshes.",
    )
    parser.add_argument("--team-key", default="wilco")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--lookback-days", default=14, type=int)
    parser.add_argument("--include-watched", action="store_true")
    parser.add_argument(
        "--include-recent",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--include-active",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--include-schedule", action="store_true")
    parser.add_argument("--max-matches", default=25, type=int)
    parser.add_argument(
        "--build-level",
        choices=BUILD_LEVELS,
        default="team",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-unchanged",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--allow-over-max", action="store_true")
    return parser


def build_download_raw_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli download-raw",
        description=(
            "Download raw SASP JSON with conservative desktop pacing."
        ),
    )
    parser.add_argument("--match-ids", required=True)
    parser.add_argument("--output-dir", default=Path("output"), type=Path)
    parser.add_argument("--include-schedule", action="store_true")
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--requests-per-window", default=4, type=int)
    parser.add_argument("--window-seconds", default=30.0, type=float)
    parser.add_argument("--retry-count", default=3, type=int)
    parser.add_argument(
        "--retry-backoff-seconds",
        default=30.0,
        type=float,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-matches", default=25, type=int)
    return parser


def build_raw_status_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli raw-status",
        description="Inventory local raw JSON without making API calls.",
    )
    parser.add_argument("--output-dir", default=Path("output"), type=Path)
    parser.add_argument("--match-index", type=Path)
    parser.add_argument("--match-ids", default="")
    parser.add_argument("--require-schedule", action="store_true")
    parser.add_argument("--team-key", default="")
    return parser


def build_history_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli history-build",
        description="Build Wilco historical analytics from local outputs.",
    )
    parser.add_argument("--team-key", default="wilco")
    parser.add_argument("--output-dir", default=Path("output"), type=Path)
    parser.add_argument("--match-ids", default="")
    parser.add_argument("--match-ids-file", type=Path)
    parser.add_argument("--match-index", type=Path)
    parser.add_argument("--backfill-results", type=Path)
    parser.add_argument(
        "--include-partial",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--include-no-scores",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--exclude-no-scores-from-performance",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--min-athlete-matches", default=2, type=int)
    parser.add_argument(
        "--workbook",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser


def build_history_insights_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli history-insights",
        description="Build coach insights from local Phase 6A history.",
    )
    parser.add_argument("--team-key", default="wilco")
    parser.add_argument("--output-dir", default=Path("output"), type=Path)
    parser.add_argument("--history-dir", type=Path)
    parser.add_argument("--season")
    parser.add_argument("--min-scored-matches", default=2, type=int)
    parser.add_argument("--current-season-only", action="store_true")
    parser.add_argument("--include-placeholders", action="store_true")
    parser.add_argument(
        "--workbook",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser


def build_records_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli records-build",
        description="Build Wilco records and personal-record reports.",
    )
    parser.add_argument("--team-key", default="wilco")
    parser.add_argument("--output-dir", default=Path("output"), type=Path)
    parser.add_argument("--records-dir", type=Path)
    parser.add_argument("--history-dir", type=Path)
    parser.add_argument("--match-id", type=int)
    parser.add_argument("--match-ids", default="")
    parser.add_argument("--match-ids-file", type=Path)
    parser.add_argument("--season")
    parser.add_argument("--include-placeholders", action="store_true")
    parser.add_argument(
        "--workbook",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser


def build_nationals_readiness_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wilco_as_reporting.cli nationals-readiness",
        description="Build a private coach-facing Nationals readiness brief.",
    )
    parser.add_argument("--team-key", default="wilco")
    parser.add_argument("--match-id", default=671, type=int)
    parser.add_argument("--output-dir", default=Path("output"), type=Path)
    parser.add_argument("--history-dir", type=Path)
    parser.add_argument("--records-dir", type=Path)
    parser.add_argument("--season")
    parser.add_argument(
        "--workbook",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--include-limited-history",
        action=argparse.BooleanOptionalAction,
        default=True,
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


def run_backfill_command(arguments: Sequence[str]) -> int:
    args = build_backfill_parser().parse_args(arguments)
    dry_run = args.dry_run or "--build-level" not in arguments
    try:
        profile = load_team_profile(args.team_key)
        result = run_backfill(
            output_root=args.output_dir,
            profile=profile,
            match_ids=_parse_integer_list(args.match_ids),
            from_date=args.from_date,
            to_date=args.to_date,
            post_types=_parse_text_list(args.post_types),
            build_level=args.build_level,
            include_schedule=args.include_schedule,
            max_matches=args.max_matches,
            dry_run=dry_run,
            overwrite=args.overwrite,
            skip_unchanged=args.skip_unchanged,
            allow_over_max=args.allow_over_max,
        )
    except (
        BatchRefreshError,
        SaspApiError,
        TeamProfileError,
        ValueError,
    ) as exc:
        print(f"Error: {exc}")
        return 1
    _print_batch_summary("backfill", result)
    return 0 if result.failed_count == 0 else 1


def run_incremental_refresh_command(
    arguments: Sequence[str],
) -> int:
    args = build_incremental_refresh_parser().parse_args(arguments)
    dry_run = args.dry_run or "--build-level" not in arguments
    try:
        profile = load_team_profile(args.team_key)
        result = run_incremental_refresh(
            output_root=args.output_dir,
            profile=profile,
            lookback_days=args.lookback_days,
            include_watched=args.include_watched,
            include_recent=args.include_recent,
            include_active=args.include_active,
            include_schedule=args.include_schedule,
            max_matches=args.max_matches,
            dry_run=dry_run,
            build_level=args.build_level,
            skip_unchanged=args.skip_unchanged,
            overwrite=args.overwrite,
            allow_over_max=args.allow_over_max,
        )
    except (
        BatchRefreshError,
        SaspApiError,
        TeamProfileError,
        ValueError,
    ) as exc:
        print(f"Error: {exc}")
        return 1
    _print_batch_summary("incremental refresh", result)
    return 0 if result.failed_count == 0 else 1


def run_download_raw(arguments: Sequence[str]) -> int:
    args = build_download_raw_parser().parse_args(arguments)
    print(
        "rate limit: "
        f"{args.requests_per_window} request(s) per "
        f"{args.window_seconds:g} seconds"
    )
    print(
        "retry policy: "
        f"{args.retry_count} retry attempt(s), "
        f"{args.retry_backoff_seconds:g}-second base backoff"
    )
    try:
        result = download_raw_matches(
            match_ids=_parse_integer_list(args.match_ids),
            output_root=args.output_dir,
            include_schedule=args.include_schedule,
            skip_existing=args.skip_existing,
            overwrite=args.overwrite,
            requests_per_window=args.requests_per_window,
            window_seconds=args.window_seconds,
            retry_count=args.retry_count,
            retry_backoff_seconds=args.retry_backoff_seconds,
            dry_run=args.dry_run,
            max_matches=args.max_matches,
        )
    except (RawDownloadError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1
    print(f"download dry run: {result.dry_run}")
    print(f"planned endpoints: {result.planned_count}")
    print(f"valid downloads: {result.valid_download_count}")
    print(
        "no-content downloads: "
        f"{result.no_content_download_count}"
    )
    print(f"skipped valid: {result.skipped_valid_count}")
    print(
        "skipped no-content: "
        f"{result.skipped_no_content_count}"
    )
    print(f"failed endpoints: {result.failed_count}")
    print(f"download plan: {result.plan_path}")
    print(f"download results: {result.results_path}")
    print(f"download errors: {result.errors_path}")
    return 0 if result.failed_count == 0 else 1


def run_raw_status(arguments: Sequence[str]) -> int:
    args = build_raw_status_parser().parse_args(arguments)
    try:
        result = build_raw_inventory(
            output_root=args.output_dir,
            match_index=args.match_index,
            match_ids=_parse_integer_list(args.match_ids),
            require_schedule=args.require_schedule,
            team_key=args.team_key,
        )
    except (RawInventoryError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1
    print(f"total matches checked: {result.total_matches}")
    print(f"total files checked: {result.total_files}")
    print(f"useful files: {result.useful_files_count}")
    print(f"no-content files: {result.no_content_files_count}")
    print(f"invalid files: {result.invalid_files_count}")
    print(f"core complete matches: {result.core_complete_count}")
    print(f"incomplete matches: {result.incomplete_match_count}")
    print(f"local inventory: {result.local_inventory_path}")
    print(f"coverage: {result.coverage_path}")
    print(f"missing core JSON: {result.missing_path}")
    print(f"content issues: {result.content_issues_path}")
    print(f"summary: {result.summary_path}")
    return 0


def run_history_build(arguments: Sequence[str]) -> int:
    args = build_history_parser().parse_args(arguments)
    try:
        profile = load_team_profile(args.team_key)
        result = build_history(
            output_root=args.output_dir,
            profile=profile,
            match_ids=_parse_integer_list(args.match_ids),
            match_ids_file=args.match_ids_file,
            match_index=args.match_index,
            backfill_results=args.backfill_results,
            include_partial=args.include_partial,
            include_no_scores=args.include_no_scores,
            exclude_no_scores_from_performance=(
                args.exclude_no_scores_from_performance
            ),
            min_athlete_matches=args.min_athlete_matches,
            workbook=args.workbook,
        )
    except (HistoryBuildError, TeamProfileError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1
    print(f"source matches: {result.source_matches}")
    print(f"Wilco matches found: {result.wilco_matches}")
    print(f"athletes found: {result.athletes}")
    print(f"disciplines found: {result.disciplines}")
    print(f"scored entries: {result.scored_entries}")
    for filename, row_count in result.row_counts.items():
        print(f"{filename}: {row_count} rows")
    if result.workbook_path:
        print(f"workbook: {result.workbook_path}")
    for warning in result.warnings[:20]:
        print(f"Warning: {warning}")
    if len(result.warnings) > 20:
        print(
            f"Warning: {len(result.warnings) - 20} additional "
            "input warnings omitted from console."
        )
    print(f"history output: {result.output_dir}")
    return 0


def run_history_insights(arguments: Sequence[str]) -> int:
    args = build_history_insights_parser().parse_args(arguments)
    try:
        result = build_history_insights(
            output_root=args.output_dir,
            team_key=args.team_key,
            history_dir=args.history_dir,
            season=args.season,
            min_scored_matches=args.min_scored_matches,
            current_season_only=args.current_season_only,
            include_placeholders=args.include_placeholders,
            workbook=args.workbook,
        )
    except (HistoryInsightsError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1
    print(f"insight season: {result.season}")
    print(f"identity issue affected rows: {result.identity_issue_rows}")
    print(f"current-season athletes: {result.current_season_athletes}")
    for filename, row_count in result.row_counts.items():
        print(f"{filename}: {row_count} rows")
    if result.workbook_path:
        print(f"workbook: {result.workbook_path}")
    print(f"history insights output: {result.history_dir}")
    return 0


def run_records_build(arguments: Sequence[str]) -> int:
    args = build_records_parser().parse_args(arguments)
    try:
        result = build_records(
            output_root=args.output_dir,
            team_key=args.team_key,
            records_dir=args.records_dir,
            history_dir=args.history_dir,
            match_id=args.match_id,
            match_ids=_parse_integer_list(args.match_ids),
            match_ids_file=args.match_ids_file,
            season=args.season,
            include_placeholders=args.include_placeholders,
            workbook=args.workbook,
        )
    except (RecordsBuildError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1
    for filename, row_count in result.row_counts.items():
        print(f"{filename}: {row_count} rows")
    print(
        "placeholder rows excluded: "
        f"{result.placeholder_rows_excluded}"
    )
    print(f"no-score rows excluded: {result.no_score_rows_excluded}")
    print(f"identity candidates: {result.identity_candidates}")
    print(f"initial PR rows: {result.initial_pr_count}")
    print(f"improved PR rows: {result.improved_pr_count}")
    print(
        "display-ineligible PR highlights: "
        f"{result.display_ineligible_count}"
    )
    if result.workbook_path:
        print(f"workbook: {result.workbook_path}")
    print(f"records output: {result.records_dir}")
    return 0


def run_nationals_readiness(arguments: Sequence[str]) -> int:
    args = build_nationals_readiness_parser().parse_args(arguments)
    try:
        profile = load_team_profile(args.team_key)
        result = build_nationals_readiness(
            output_root=args.output_dir,
            profile=profile,
            match_id=args.match_id,
            history_dir=args.history_dir,
            records_dir=args.records_dir,
            season=args.season,
            workbook=args.workbook,
            include_limited_history=args.include_limited_history,
        )
    except (
        NationalsReadinessError,
        TeamProfileError,
        ValueError,
    ) as exc:
        print(f"Error: {exc}")
        return 1
    print(f"athletes entered: {result.athletes_entered}")
    print(
        "athlete-discipline entries: "
        f"{result.athlete_discipline_entries}"
    )
    for level, count in sorted(result.readiness_counts.items()):
        print(f"readiness {level}: {count}")
    for opportunity, count in sorted(result.opportunity_counts.items()):
        print(f"PR opportunity {opportunity}: {count}")
    print(f"watchlist items: {result.watchlist_count}")
    for filename, row_count in result.row_counts.items():
        print(f"{filename}: {row_count} rows")
    if result.workbook_path:
        print(f"workbook: {result.workbook_path}")
    print(f"readiness output: {result.output_dir}")
    return 0


def _parse_integer_list(value: str) -> tuple[int, ...]:
    if not value.strip():
        return ()
    try:
        return tuple(
            int(item.strip())
            for item in value.split(",")
            if item.strip()
        )
    except ValueError as exc:
        raise ValueError(
            f"Expected comma-separated integer match IDs: {value!r}"
        ) from exc


def _parse_text_list(value: str) -> tuple[str, ...]:
    return tuple(
        item.strip().upper()
        for item in value.split(",")
        if item.strip()
    )


def _print_batch_summary(label: str, result: object) -> None:
    print(f"{label} dry run: {result.dry_run}")
    print(f"selected matches: {result.selected_count}")
    print(f"processed matches: {result.processed_count}")
    print(f"skipped matches: {result.skipped_count}")
    print(f"failed matches: {result.failed_count}")
    print(f"plan/candidates: {result.plan_path}")
    print(f"results: {result.results_path}")
    print(f"errors: {result.errors_path}")


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
    if command_arguments and command_arguments[0] == "backfill":
        return run_backfill_command(command_arguments[1:])
    if (
        command_arguments
        and command_arguments[0] == "incremental-refresh"
    ):
        return run_incremental_refresh_command(command_arguments[1:])
    if command_arguments and command_arguments[0] == "download-raw":
        return run_download_raw(command_arguments[1:])
    if command_arguments and command_arguments[0] == "raw-status":
        return run_raw_status(command_arguments[1:])
    if command_arguments and command_arguments[0] == "history-build":
        return run_history_build(command_arguments[1:])
    if command_arguments and command_arguments[0] == "history-insights":
        return run_history_insights(command_arguments[1:])
    if command_arguments and command_arguments[0] == "records-build":
        return run_records_build(command_arguments[1:])
    if command_arguments and command_arguments[0] == "nationals-readiness":
        return run_nationals_readiness(command_arguments[1:])
    return run_fetch(command_arguments)


if __name__ == "__main__":
    raise SystemExit(main())
