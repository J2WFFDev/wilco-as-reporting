"""Excel workbook generation from report-ready match tables."""

from wilco_as_reporting.workbooks.excel_writer import (
    MatchWorkbookError,
    WorkbookResult,
    build_match_workbook,
)
from wilco_as_reporting.workbooks.team_excel_writer import (
    TeamWorkbookError,
    TeamWorkbookResult,
    build_team_workbook,
)

__all__ = [
    "MatchWorkbookError",
    "TeamWorkbookError",
    "TeamWorkbookResult",
    "WorkbookResult",
    "build_match_workbook",
    "build_team_workbook",
]
