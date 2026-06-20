"""Report-ready tables built from parsed and validated match data."""

from wilco_as_reporting.reports.match_report import (
    MatchReportError,
    ReportResult,
    build_match_report,
)
from wilco_as_reporting.reports.team_report import (
    TeamReportError,
    TeamReportResult,
    build_team_report,
)

__all__ = [
    "MatchReportError",
    "ReportResult",
    "TeamReportError",
    "TeamReportResult",
    "build_match_report",
    "build_team_report",
]
