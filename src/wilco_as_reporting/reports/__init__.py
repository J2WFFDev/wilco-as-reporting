"""Report-ready tables built from parsed and validated match data."""

from wilco_as_reporting.reports.match_report import (
    MatchReportError,
    ReportResult,
    build_match_report,
)

__all__ = [
    "MatchReportError",
    "ReportResult",
    "build_match_report",
]

