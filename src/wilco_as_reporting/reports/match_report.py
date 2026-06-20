"""Build report-ready CSV tables for one SASP match."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

TEAM_SUMMARY_COLUMNS = (
    "match_id",
    "match_name",
    "team_name",
    "athlete_count",
    "entry_count",
    "discipline_count",
    "squad_count",
    "validation_error_count",
    "validation_warning_count",
    "validation_review_count",
    "best_individual_place",
    "best_squad_place",
    "notes",
)

ATHLETE_SUMMARY_COLUMNS = (
    "match_id",
    "athlete_id",
    "athlete_name",
    "team_name",
    "entry_count",
    "disciplines",
    "best_place",
    "best_rank_scope",
    "best_score_seconds",
    "total_review_findings",
    "total_warning_findings",
    "total_error_findings",
    "notes",
)

AWARD_RESULT_COLUMNS = (
    "match_id",
    "discipline",
    "leaderboard_name",
    "leaderboard_type",
    "rank_type",
    "rank_scope",
    "award_scope",
    "place",
    "field_size",
    "athlete_name",
    "team_name",
    "class",
    "score_seconds",
    "inside_award_places",
    "margin_to_leader",
    "margin_to_previous_place",
)

SQUAD_SUMMARY_COLUMNS = (
    "match_id",
    "discipline",
    "rank_scope",
    "award_scope",
    "squad_place",
    "squad_name",
    "squad_score_seconds",
    "athlete_count",
    "margin_to_leader",
    "margin_to_previous_place",
    "inside_award_places",
    "athlete_1_name",
    "athlete_1_score",
    "athlete_2_name",
    "athlete_2_score",
    "athlete_3_name",
    "athlete_3_score",
    "athlete_4_name",
    "athlete_4_score",
)

STAGE_PERFORMANCE_COLUMNS = (
    "match_id",
    "athlete_id",
    "athlete_name",
    "team_name",
    "class",
    "discipline",
    "stage_number",
    "stage_name",
    "stage_score_seconds",
    "fastest_string_seconds",
    "scored_avg_string_seconds",
    "dropped_string_count",
    "penalty_count",
)

VALIDATION_ROLLUP_COLUMNS = (
    "match_id",
    "severity",
    "check_name",
    "finding_count",
    "status",
    "notes",
)

COACH_REVIEW_COLUMNS = (
    "match_id",
    "severity",
    "check_name",
    "finding_type",
    "entity_type",
    "athlete_name",
    "team_name",
    "discipline",
    "stage_number",
    "stage_name",
    "message",
    "expected_value",
    "actual_value",
    "difference",
)


class MatchReportError(RuntimeError):
    """Raised when report-ready tables cannot be built."""


@dataclass(frozen=True)
class ReportResult:
    team_summary_path: Path
    athlete_summary_path: Path
    award_results_path: Path
    squad_summary_path: Path
    stage_performance_path: Path
    validation_rollup_path: Path
    coach_review_queue_path: Path
    row_counts: dict[str, int]


def build_match_report(
    match_id: int,
    output_dir: Path | str,
) -> ReportResult:
    """Build report-ready CSV tables from parsed and validated inputs."""
    output_path = Path(output_dir)
    tables_dir = output_path / "tables"
    validation_dir = output_path / "validation"
    report_dir = output_path / "report_tables"

    match_scores = _read_csv(tables_dir / "match_scores.csv")
    rankings = _read_csv(tables_dir / "rankings.csv")
    squad_results = _read_csv(tables_dir / "squad_results.csv")
    stage_scores = _read_csv(tables_dir / "stage_scores.csv")
    validation_summary = _read_csv(
        validation_dir / "validation_summary.csv"
    )
    validation_findings = _read_csv(
        validation_dir / "validation_findings.csv"
    )
    _read_csv(validation_dir / "match_score_reconciliation.csv")
    _read_csv(validation_dir / "stage_score_reconciliation.csv")
    _read_csv(validation_dir / "squad_score_reconciliation.csv")

    _confirm_match_ids(
        match_id,
        match_scores,
        rankings,
        squad_results,
        stage_scores,
        validation_summary,
        validation_findings,
    )

    athlete_team_map = _athlete_team_map(match_scores)
    squad_attributions = _attribute_squads(
        squad_results,
        athlete_team_map,
    )
    team_summary = _build_team_summary(
        match_id,
        match_scores,
        rankings,
        squad_results,
        validation_findings,
        squad_attributions,
    )
    athlete_summary = _build_athlete_summary(
        match_id,
        match_scores,
        rankings,
        validation_findings,
    )
    award_results = _build_award_results(rankings)
    squad_summary = _select_columns(
        squad_results,
        SQUAD_SUMMARY_COLUMNS,
    )
    stage_performance = _select_columns(
        stage_scores,
        STAGE_PERFORMANCE_COLUMNS,
    )
    validation_rollup = _build_validation_rollup(validation_summary)
    coach_review_queue = _build_coach_review_queue(validation_findings)

    _ensure_directory(report_dir)
    outputs = {
        "team_summary.csv": (
            TEAM_SUMMARY_COLUMNS,
            team_summary,
        ),
        "athlete_summary.csv": (
            ATHLETE_SUMMARY_COLUMNS,
            athlete_summary,
        ),
        "award_results.csv": (
            AWARD_RESULT_COLUMNS,
            award_results,
        ),
        "squad_summary.csv": (
            SQUAD_SUMMARY_COLUMNS,
            squad_summary,
        ),
        "stage_performance.csv": (
            STAGE_PERFORMANCE_COLUMNS,
            stage_performance,
        ),
        "validation_rollup.csv": (
            VALIDATION_ROLLUP_COLUMNS,
            validation_rollup,
        ),
        "coach_review_queue.csv": (
            COACH_REVIEW_COLUMNS,
            coach_review_queue,
        ),
    }
    paths: dict[str, Path] = {}
    row_counts: dict[str, int] = {}
    for filename, (columns, rows) in outputs.items():
        path = report_dir / filename
        _write_csv(path, columns, rows)
        paths[filename] = path
        row_counts[filename] = len(rows)

    return ReportResult(
        team_summary_path=paths["team_summary.csv"],
        athlete_summary_path=paths["athlete_summary.csv"],
        award_results_path=paths["award_results.csv"],
        squad_summary_path=paths["squad_summary.csv"],
        stage_performance_path=paths["stage_performance.csv"],
        validation_rollup_path=paths["validation_rollup.csv"],
        coach_review_queue_path=paths["coach_review_queue.csv"],
        row_counts=row_counts,
    )


def _build_team_summary(
    match_id: int,
    match_scores: list[dict[str, str]],
    rankings: list[dict[str, str]],
    squad_results: list[dict[str, str]],
    findings: list[dict[str, str]],
    squad_attributions: list[tuple[str, bool]],
) -> list[dict[str, Any]]:
    teams = sorted(
        {row.get("team_name", "") for row in match_scores},
        key=str.casefold,
    )
    match_name = next(
        (
            row.get("match_name", "")
            for row in match_scores
            if row.get("match_name", "")
        ),
        "",
    )
    rows: list[dict[str, Any]] = []

    for team_name in teams:
        entries = [
            row for row in match_scores if row.get("team_name") == team_name
        ]
        official_rankings = [
            row
            for row in rankings
            if row.get("team_name") == team_name
            and row.get("award_scope") != "Comparison"
        ]
        team_findings = [
            row for row in findings if row.get("team_name") == team_name
        ]
        attributed_squads = [
            (squad, partial)
            for squad, (attributed_team, partial) in zip(
                squad_results,
                squad_attributions,
            )
            if attributed_team == team_name
        ]
        partial_count = sum(partial for _, partial in attributed_squads)
        notes = (
            "Squads attributed from listed athlete team membership."
            if not partial_count
            else (
                "Squads attributed from listed athlete team membership; "
                f"{partial_count} squad(s) included unmatched placeholders."
            )
        )
        rows.append(
            {
                "match_id": match_id,
                "match_name": match_name,
                "team_name": team_name,
                "athlete_count": len(
                    {
                        _athlete_identity(row)
                        for row in entries
                    }
                ),
                "entry_count": len(entries),
                "discipline_count": len(
                    {row.get("discipline", "") for row in entries}
                ),
                "squad_count": len(attributed_squads),
                "validation_error_count": _severity_count(
                    team_findings,
                    "ERROR",
                ),
                "validation_warning_count": _severity_count(
                    team_findings,
                    "WARNING",
                ),
                "validation_review_count": _severity_count(
                    team_findings,
                    "REVIEW",
                ),
                "best_individual_place": _minimum_integer(
                    row.get("place") for row in official_rankings
                ),
                "best_squad_place": _minimum_integer(
                    squad.get("squad_place")
                    for squad, _ in attributed_squads
                ),
                "notes": notes,
            }
        )

    return rows


def _build_athlete_summary(
    match_id: int,
    match_scores: list[dict[str, str]],
    rankings: list[dict[str, str]],
    findings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    entries_by_athlete: dict[tuple[str, str, str], list[dict[str, str]]] = (
        defaultdict(list)
    )
    for row in match_scores:
        entries_by_athlete[_athlete_identity(row)].append(row)

    official_rankings: dict[tuple[str, str], list[dict[str, str]]] = (
        defaultdict(list)
    )
    for row in rankings:
        if row.get("award_scope") != "Comparison":
            official_rankings[
                (row.get("athlete_name", ""), row.get("team_name", ""))
            ].append(row)

    findings_by_athlete: dict[tuple[str, str], list[dict[str, str]]] = (
        defaultdict(list)
    )
    for row in findings:
        findings_by_athlete[
            (row.get("athlete_name", ""), row.get("team_name", ""))
        ].append(row)

    rows: list[dict[str, Any]] = []
    for identity, entries in entries_by_athlete.items():
        athlete_id, athlete_name, team_name = identity
        athlete_rankings = official_rankings.get(
            (athlete_name, team_name),
            [],
        )
        best_ranking = min(
            athlete_rankings,
            key=lambda row: (
                _integer(row.get("place")) or 10**9,
                _number(row.get("score_seconds")) or 10**9,
                row.get("rank_scope", ""),
            ),
            default=None,
        )
        athlete_findings = findings_by_athlete.get(
            (athlete_name, team_name),
            [],
        )
        notes: list[str] = []
        if not athlete_name:
            notes.append("Athlete name missing in parsed source.")
        if len(entries) > len(
            {row.get("discipline", "") for row in entries}
        ):
            notes.append("Repeated athlete/discipline entry preserved.")

        rows.append(
            {
                "match_id": match_id,
                "athlete_id": athlete_id,
                "athlete_name": athlete_name,
                "team_name": team_name,
                "entry_count": len(entries),
                "disciplines": "; ".join(
                    sorted(
                        {
                            row.get("discipline", "")
                            for row in entries
                            if row.get("discipline", "")
                        },
                        key=str.casefold,
                    )
                ),
                "best_place": (
                    best_ranking.get("place", "")
                    if best_ranking
                    else ""
                ),
                "best_rank_scope": (
                    best_ranking.get("rank_scope", "")
                    if best_ranking
                    else ""
                ),
                "best_score_seconds": _minimum_number(
                    row.get("match_score_seconds") for row in entries
                ),
                "total_review_findings": _severity_count(
                    athlete_findings,
                    "REVIEW",
                ),
                "total_warning_findings": _severity_count(
                    athlete_findings,
                    "WARNING",
                ),
                "total_error_findings": _severity_count(
                    athlete_findings,
                    "ERROR",
                ),
                "notes": " ".join(notes),
            }
        )

    rows.sort(
        key=lambda row: (
            row["team_name"].casefold(),
            row["athlete_name"].casefold(),
            row["athlete_id"],
        )
    )
    return rows


def _build_award_results(
    rankings: list[dict[str, str]],
) -> list[dict[str, str]]:
    selected = [
        row
        for row in rankings
        if row.get("award_scope") == "Comparison"
        or _truthy(row.get("inside_award_places"))
    ]
    return _select_columns(selected, AWARD_RESULT_COLUMNS)


def _build_validation_rollup(
    validation_summary: list[dict[str, str]],
) -> list[dict[str, str]]:
    return [
        {
            "match_id": row.get("match_id", ""),
            "severity": row.get("severity", ""),
            "check_name": row.get("check_name", ""),
            "finding_count": row.get("finding_count", ""),
            "status": row.get("status", ""),
            "notes": row.get("notes", ""),
        }
        for row in validation_summary
    ]


def _build_coach_review_queue(
    findings: list[dict[str, str]],
) -> list[dict[str, str]]:
    selected = [
        row
        for row in findings
        if row.get("severity") in {"ERROR", "WARNING", "REVIEW"}
    ]
    severity_order = {"ERROR": 0, "WARNING": 1, "REVIEW": 2}
    selected.sort(
        key=lambda row: (
            severity_order[row["severity"]],
            row.get("team_name", "").casefold(),
            row.get("athlete_name", "").casefold(),
            row.get("discipline", "").casefold(),
            _integer(row.get("stage_number")) or 0,
            row.get("check_name", ""),
        )
    )
    return _select_columns(selected, COACH_REVIEW_COLUMNS)


def _attribute_squads(
    squad_results: list[dict[str, str]],
    athlete_team_map: dict[str, str],
) -> list[tuple[str, bool]]:
    attributions: list[tuple[str, bool]] = []
    for squad in squad_results:
        listed_names = [
            squad.get(f"athlete_{number}_name", "")
            for number in range(1, 5)
        ]
        matched_teams = [
            athlete_team_map[name]
            for name in listed_names
            if name in athlete_team_map
        ]
        unique_teams = set(matched_teams)
        if len(unique_teams) != 1:
            attributions.append(("", True))
            continue
        attributions.append(
            (
                next(iter(unique_teams)),
                len(matched_teams) != len(listed_names),
            )
        )
    return attributions


def _athlete_team_map(
    match_scores: list[dict[str, str]],
) -> dict[str, str]:
    teams_by_name: dict[str, set[str]] = defaultdict(set)
    for row in match_scores:
        athlete_name = row.get("athlete_name", "")
        team_name = row.get("team_name", "")
        if athlete_name and team_name:
            teams_by_name[athlete_name].add(team_name)
    return {
        name: next(iter(teams))
        for name, teams in teams_by_name.items()
        if len(teams) == 1
    }


def _athlete_identity(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("athlete_id", ""),
        row.get("athlete_name", ""),
        row.get("team_name", ""),
    )


def _severity_count(
    findings: list[dict[str, str]],
    severity: str,
) -> int:
    return sum(row.get("severity") == severity for row in findings)


def _minimum_integer(values: Iterable[Any]) -> int | str:
    parsed = [
        value
        for value in (_integer(item) for item in values)
        if value is not None
    ]
    return min(parsed) if parsed else ""


def _minimum_number(values: Iterable[Any]) -> float | int | str:
    parsed = [
        value
        for value in (_number(item) for item in values)
        if value is not None
    ]
    return _clean_number(min(parsed)) if parsed else ""


def _select_columns(
    rows: Iterable[dict[str, str]],
    columns: Iterable[str],
) -> list[dict[str, str]]:
    return [
        {column: row.get(column, "") for column in columns}
        for row in rows
    ]


def _confirm_match_ids(
    match_id: int,
    *tables: list[dict[str, str]],
) -> None:
    expected = str(match_id)
    for rows in tables:
        unexpected = {
            row.get("match_id", "")
            for row in rows
            if row.get("match_id", "") != expected
        }
        if unexpected:
            raise MatchReportError(
                f"Input tables contain unexpected match IDs: "
                f"{sorted(unexpected)}"
            )


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            return list(csv.DictReader(source))
    except FileNotFoundError as exc:
        raise MatchReportError(f"Missing report input: {path}") from exc
    except (OSError, csv.Error) as exc:
        raise MatchReportError(
            f"Could not read report input {path}: {exc}"
        ) from exc


def _write_csv(
    path: Path,
    fieldnames: Iterable[str],
    rows: Iterable[dict[str, Any]],
) -> None:
    try:
        with path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(
                target,
                fieldnames=fieldnames,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, csv.Error) as exc:
        raise MatchReportError(
            f"Could not write report table {path}: {exc}"
        ) from exc


def _ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MatchReportError(
            f"Could not create report table directory {path}: {exc}"
        ) from exc
    if not path.is_dir():
        raise MatchReportError(
            f"Report table path is not a directory: {path}"
        )


def _integer(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_number(value: float) -> float | int:
    return int(value) if value.is_integer() else value


def _truthy(value: Any) -> bool:
    return str(value).strip().casefold() == "true"

