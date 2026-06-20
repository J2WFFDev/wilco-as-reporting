"""End-to-end single-match report pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wilco_as_reporting.api.sasp_client import MatchSnapshots, SaspClient
from wilco_as_reporting.nationals_ops import (
    NationalsOpsResult,
    build_nationals_operations,
)
from wilco_as_reporting.parsers import ParseResult, parse_match
from wilco_as_reporting.reports import (
    ReportResult,
    TeamReportResult,
    build_match_report,
    build_team_report,
)
from wilco_as_reporting.team_profiles import TeamProfile
from wilco_as_reporting.validators import ValidationResult, validate_match
from wilco_as_reporting.workbooks import (
    TeamWorkbookResult,
    WorkbookResult,
    build_match_workbook,
    build_team_workbook,
)


@dataclass(frozen=True)
class BuildResult:
    snapshots: MatchSnapshots
    parse_result: ParseResult
    validation_result: ValidationResult
    report_result: ReportResult
    workbook_result: WorkbookResult


@dataclass(frozen=True)
class TeamBuildResult:
    full_build: BuildResult
    team_report_result: TeamReportResult
    team_workbook_result: TeamWorkbookResult


@dataclass(frozen=True)
class NationalsBuildResult:
    team_build: TeamBuildResult
    operations_result: NationalsOpsResult


def build_single_match(
    match_id: int,
    output_dir: Path | str,
    *,
    overwrite: bool = False,
    include_schedule: bool = False,
    client: SaspClient | None = None,
) -> BuildResult:
    """Fetch, parse, validate, report, and build a workbook for one match."""
    sasp_client = client or SaspClient()
    snapshots = sasp_client.fetch_match_snapshots(
        match_id=match_id,
        output_dir=output_dir,
        overwrite=overwrite,
        include_schedule=include_schedule,
    )
    parse_result = parse_match(
        match_id=match_id,
        output_dir=output_dir,
    )
    validation_result = validate_match(
        match_id=match_id,
        output_dir=output_dir,
    )
    report_result = build_match_report(
        match_id=match_id,
        output_dir=output_dir,
    )
    workbook_result = build_match_workbook(
        match_id=match_id,
        output_dir=output_dir,
    )
    return BuildResult(
        snapshots=snapshots,
        parse_result=parse_result,
        validation_result=validation_result,
        report_result=report_result,
        workbook_result=workbook_result,
    )


def build_team_match(
    match_id: int,
    output_dir: Path | str,
    profile: TeamProfile,
    *,
    overwrite: bool = False,
    include_schedule: bool = False,
    client: SaspClient | None = None,
) -> TeamBuildResult:
    """Build full-match and team coaching artifacts."""
    full_build = build_single_match(
        match_id=match_id,
        output_dir=output_dir,
        overwrite=overwrite,
        include_schedule=include_schedule,
        client=client,
    )
    team_report_result = build_team_report(
        match_id=match_id,
        output_dir=output_dir,
        profile=profile,
    )
    team_workbook_result = build_team_workbook(
        match_id=match_id,
        output_dir=output_dir,
        profile=profile,
    )
    return TeamBuildResult(
        full_build=full_build,
        team_report_result=team_report_result,
        team_workbook_result=team_workbook_result,
    )


def build_nationals_match(
    match_id: int,
    output_dir: Path | str,
    profile: TeamProfile,
    *,
    snapshot_label: str = "manual",
    overwrite: bool = False,
    include_schedule: bool = False,
    client: SaspClient | None = None,
) -> NationalsBuildResult:
    """Build current team artifacts and a preserved operations snapshot."""
    team_build = build_team_match(
        match_id=match_id,
        output_dir=output_dir,
        profile=profile,
        overwrite=overwrite,
        include_schedule=include_schedule,
        client=client,
    )
    operations_result = build_nationals_operations(
        match_id=match_id,
        output_dir=output_dir,
        profile=profile,
        snapshot_label=snapshot_label,
    )
    return NationalsBuildResult(
        team_build=team_build,
        operations_result=operations_result,
    )
