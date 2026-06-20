"""End-to-end single-match report pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wilco_as_reporting.api.sasp_client import MatchSnapshots, SaspClient
from wilco_as_reporting.parsers import ParseResult, parse_match
from wilco_as_reporting.reports import ReportResult, build_match_report
from wilco_as_reporting.validators import ValidationResult, validate_match
from wilco_as_reporting.workbooks import WorkbookResult, build_match_workbook


@dataclass(frozen=True)
class BuildResult:
    snapshots: MatchSnapshots
    parse_result: ParseResult
    validation_result: ValidationResult
    report_result: ReportResult
    workbook_result: WorkbookResult


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

