"""Build coach-focused report tables for one configured team."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from wilco_as_reporting.team_profiles import TeamProfile

TEAM_SUMMARY_COLUMNS = (
    "match_id",
    "match_name",
    "team_key",
    "team_name",
    "athlete_count",
    "entry_count",
    "discipline_count",
    "squad_count",
    "official_award_count",
    "comparison_top_10_count",
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
    "class",
    "gender",
    "entry_count",
    "disciplines",
    "best_official_place",
    "best_official_scope",
    "best_comparison_place",
    "best_score_seconds",
    "award_count",
    "review_count",
    "warning_count",
    "error_count",
    "notes",
)

AWARD_COLUMNS = (
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

COMPARISON_COLUMNS = tuple(
    column
    for column in AWARD_COLUMNS
    if column != "inside_award_places"
)

SQUAD_COLUMNS = (
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
    "notes",
)

STAGE_COLUMNS = (
    "match_id",
    "athlete_id",
    "athlete_name",
    "class",
    "gender",
    "discipline",
    "stage_number",
    "stage_name",
    "stage_score_seconds",
    "fastest_string_seconds",
    "scored_avg_string_seconds",
    "dropped_string_count",
    "penalty_count",
    "coach_flag",
    "coach_note",
)

REVIEW_COLUMNS = (
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
    "coach_note",
)


class TeamReportError(RuntimeError):
    """Raised when team report tables cannot be built."""


@dataclass(frozen=True)
class TeamReportResult:
    team_summary_path: Path
    athlete_summary_path: Path
    award_highlights_path: Path
    comparison_results_path: Path
    squad_summary_path: Path
    stage_coach_view_path: Path
    coach_review_queue_path: Path
    row_counts: dict[str, int]
    limitations: tuple[str, ...]


def build_team_report(
    match_id: int,
    output_dir: Path | str,
    profile: TeamProfile,
) -> TeamReportResult:
    """Build coach-focused report tables for a configured team."""
    output_path = Path(output_dir)
    tables_dir = output_path / "tables"
    report_dir = output_path / "report_tables"
    team_dir = (
        output_path
        / "team_report_tables"
        / profile.team_key
    )

    match_scores = _read_csv(tables_dir / "match_scores.csv")
    rankings = _read_csv(tables_dir / "rankings.csv")
    squad_results = _read_csv(tables_dir / "squad_results.csv")
    stage_scores = _read_csv(tables_dir / "stage_scores.csv")
    award_results = _read_csv(report_dir / "award_results.csv")
    coach_queue = _read_csv(report_dir / "coach_review_queue.csv")
    _confirm_match_ids(
        match_id,
        match_scores,
        rankings,
        squad_results,
        stage_scores,
        award_results,
        coach_queue,
    )

    team_entries = [
        row
        for row in match_scores
        if profile.matches_name(row.get("team_name"))
    ]
    team_stage_rows = [
        row
        for row in stage_scores
        if profile.matches_name(row.get("team_name"))
    ]
    team_findings = [
        row
        for row in coach_queue
        if profile.matches_name(row.get("team_name"))
    ]
    official_awards = [
        row
        for row in award_results
        if profile.matches_name(row.get("team_name"))
        and row.get("award_scope") != "Comparison"
        and _truthy(row.get("inside_award_places"))
    ]
    comparisons = [
        row
        for row in award_results
        if profile.matches_name(row.get("team_name"))
        and row.get("award_scope") == "Comparison"
    ]
    squad_rows = _select_team_squads(
        squad_results,
        match_scores,
        profile,
    )
    limitations = _report_limitations(
        team_entries,
        official_awards,
        comparisons,
    )

    team_summary = _build_team_summary(
        match_id,
        profile,
        team_entries,
        official_awards,
        comparisons,
        squad_rows,
        team_findings,
        limitations,
    )
    athlete_summary = _build_athlete_summary(
        match_id,
        team_entries,
        official_awards,
        comparisons,
        team_findings,
    )
    stage_coach_view = [
        {
            **_select(row, STAGE_COLUMNS[:-2]),
            **_coach_stage_context(row),
        }
        for row in team_stage_rows
    ]
    review_queue = [
        {
            **_select(row, REVIEW_COLUMNS[:-1]),
            "coach_note": _finding_coach_note(row),
        }
        for row in team_findings
    ]

    _ensure_directory(team_dir)
    outputs = {
        "wilco_team_summary.csv": (
            TEAM_SUMMARY_COLUMNS,
            team_summary,
        ),
        "wilco_athlete_summary.csv": (
            ATHLETE_SUMMARY_COLUMNS,
            athlete_summary,
        ),
        "wilco_award_highlights.csv": (
            AWARD_COLUMNS,
            [_select(row, AWARD_COLUMNS) for row in official_awards],
        ),
        "wilco_comparison_results.csv": (
            COMPARISON_COLUMNS,
            [_select(row, COMPARISON_COLUMNS) for row in comparisons],
        ),
        "wilco_squad_summary.csv": (
            SQUAD_COLUMNS,
            squad_rows,
        ),
        "wilco_stage_coach_view.csv": (
            STAGE_COLUMNS,
            stage_coach_view,
        ),
        "wilco_coach_review_queue.csv": (
            REVIEW_COLUMNS,
            review_queue,
        ),
    }
    paths: dict[str, Path] = {}
    row_counts: dict[str, int] = {}
    for filename, (columns, rows) in outputs.items():
        path = team_dir / filename
        _write_csv(path, columns, rows)
        paths[filename] = path
        row_counts[filename] = len(rows)

    return TeamReportResult(
        team_summary_path=paths["wilco_team_summary.csv"],
        athlete_summary_path=paths["wilco_athlete_summary.csv"],
        award_highlights_path=paths["wilco_award_highlights.csv"],
        comparison_results_path=paths["wilco_comparison_results.csv"],
        squad_summary_path=paths["wilco_squad_summary.csv"],
        stage_coach_view_path=paths["wilco_stage_coach_view.csv"],
        coach_review_queue_path=paths["wilco_coach_review_queue.csv"],
        row_counts=row_counts,
        limitations=limitations,
    )


def _build_team_summary(
    match_id: int,
    profile: TeamProfile,
    entries: list[dict[str, str]],
    awards: list[dict[str, str]],
    comparisons: list[dict[str, str]],
    squads: list[dict[str, Any]],
    findings: list[dict[str, str]],
    limitations: tuple[str, ...],
) -> list[dict[str, Any]]:
    match_name = next(
        (
            row.get("match_name", "")
            for row in entries
            if row.get("match_name")
        ),
        f"Match {match_id}",
    )
    notes = [profile.notes]
    notes.extend(limitations)
    partial_squads = sum(
        "partial attribution" in row.get("notes", "").casefold()
        for row in squads
    )
    if partial_squads:
        notes.append(
            f"{partial_squads} squad(s) include placeholder members."
        )
    return [
        {
            "match_id": match_id,
            "match_name": match_name,
            "team_key": profile.team_key,
            "team_name": profile.team_name,
            "athlete_count": len(
                {
                    (
                        row.get("athlete_id", ""),
                        row.get("athlete_name", ""),
                    )
                    for row in entries
                }
            ),
            "entry_count": len(entries),
            "discipline_count": len(
                {
                    row.get("discipline", "")
                    for row in entries
                    if row.get("discipline")
                }
            ),
            "squad_count": len(squads),
            "official_award_count": (
                len(awards)
                + sum(
                    _truthy(row.get("inside_award_places"))
                    for row in squads
                )
            ),
            "comparison_top_10_count": sum(
                (_integer(row.get("place")) or 10**9) <= 10
                for row in comparisons
            ),
            "validation_error_count": _severity_count(
                findings,
                "ERROR",
            ),
            "validation_warning_count": _severity_count(
                findings,
                "WARNING",
            ),
            "validation_review_count": _severity_count(
                findings,
                "REVIEW",
            ),
            "best_individual_place": _minimum_integer(
                row.get("place") for row in awards
            ),
            "best_squad_place": _minimum_integer(
                row.get("squad_place") for row in squads
            ),
            "notes": " ".join(
                [
                    *(
                        note
                        for note in notes
                        if note
                    ),
                    (
                        "Official award count includes individual and "
                        "squad award placements."
                    ),
                ]
            ),
        }
    ]


def _report_limitations(
    entries: list[dict[str, str]],
    awards: list[dict[str, str]],
    comparisons: list[dict[str, str]],
) -> tuple[str, ...]:
    limitations: list[str] = []
    if not entries:
        limitations.append(
            "No team entries were found in parsed match data."
        )
    missing_scores = sum(
        not row.get("match_score_seconds")
        for row in entries
    )
    if missing_scores:
        limitations.append(
            f"{missing_scores} team entries do not yet have final scores."
        )
    if not awards:
        limitations.append(
            "No official individual award rows are currently available."
        )
    if not comparisons:
        limitations.append(
            "No overall comparison rows are currently available."
        )
    return tuple(limitations)


def _build_athlete_summary(
    match_id: int,
    entries: list[dict[str, str]],
    awards: list[dict[str, str]],
    comparisons: list[dict[str, str]],
    findings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    entries_by_identity: dict[
        tuple[str, str],
        list[dict[str, str]],
    ] = defaultdict(list)
    for row in entries:
        entries_by_identity[
            (
                row.get("athlete_id", ""),
                row.get("athlete_name", ""),
            )
        ].append(row)

    awards_by_name = _rows_by_athlete_name(awards)
    comparisons_by_name = _rows_by_athlete_name(comparisons)
    findings_by_name = _rows_by_athlete_name(findings)
    rows: list[dict[str, Any]] = []

    for (athlete_id, athlete_name), athlete_entries in (
        entries_by_identity.items()
    ):
        athlete_awards = awards_by_name.get(athlete_name, [])
        athlete_comparisons = comparisons_by_name.get(
            athlete_name,
            [],
        )
        athlete_findings = findings_by_name.get(athlete_name, [])
        best_award = _best_placing(athlete_awards)
        notes: list[str] = []
        if not athlete_name:
            notes.append("Placeholder athlete record; name is missing.")
        if len(athlete_entries) > len(
            {
                row.get("discipline", "")
                for row in athlete_entries
            }
        ):
            notes.append("Repeated discipline entry preserved.")
        rows.append(
            {
                "match_id": match_id,
                "athlete_id": athlete_id,
                "athlete_name": athlete_name,
                "team_name": athlete_entries[0].get("team_name", ""),
                "class": _first_value(athlete_entries, "class"),
                "gender": _first_value(athlete_entries, "gender"),
                "entry_count": len(athlete_entries),
                "disciplines": "; ".join(
                    sorted(
                        {
                            row.get("discipline", "")
                            for row in athlete_entries
                            if row.get("discipline")
                        },
                        key=str.casefold,
                    )
                ),
                "best_official_place": (
                    best_award.get("place", "")
                    if best_award
                    else ""
                ),
                "best_official_scope": (
                    best_award.get("rank_scope", "")
                    if best_award
                    else ""
                ),
                "best_comparison_place": _minimum_integer(
                    row.get("place") for row in athlete_comparisons
                ),
                "best_score_seconds": _minimum_number(
                    row.get("match_score_seconds")
                    for row in athlete_entries
                ),
                "award_count": len(athlete_awards),
                "review_count": _severity_count(
                    athlete_findings,
                    "REVIEW",
                ),
                "warning_count": _severity_count(
                    athlete_findings,
                    "WARNING",
                ),
                "error_count": _severity_count(
                    athlete_findings,
                    "ERROR",
                ),
                "notes": " ".join(notes),
            }
        )
    rows.sort(
        key=lambda row: (
            row["athlete_name"].casefold(),
            row["athlete_id"],
        )
    )
    return rows


def _select_team_squads(
    squad_results: list[dict[str, str]],
    match_scores: list[dict[str, str]],
    profile: TeamProfile,
) -> list[dict[str, Any]]:
    teams_by_name: dict[str, set[str]] = defaultdict(set)
    for row in match_scores:
        athlete_name = row.get("athlete_name", "")
        team_name = row.get("team_name", "")
        if athlete_name and team_name:
            teams_by_name[athlete_name].add(team_name)

    rows: list[dict[str, Any]] = []
    for squad in squad_results:
        names = [
            squad.get(f"athlete_{number}_name", "")
            for number in range(1, 5)
        ]
        known_team_names = {
            team_name
            for name in names
            for team_name in teams_by_name.get(name, set())
        }
        matched_team_names = {
            team_name
            for team_name in known_team_names
            if profile.matches_name(team_name)
        }
        if not matched_team_names:
            continue
        if known_team_names - matched_team_names:
            continue
        unmatched_names = [
            name
            for name in names
            if not name or name not in teams_by_name
        ]
        note = "Attributed to team from all listed athlete memberships."
        if unmatched_names:
            placeholders = ", ".join(
                name or "blank"
                for name in unmatched_names
            )
            note = (
                "Partial attribution from known team members; "
                f"unmatched placeholder member(s): {placeholders}."
            )
        rows.append(
            {
                **_select(squad, SQUAD_COLUMNS[:-1]),
                "notes": note,
            }
        )
    return rows


def _coach_stage_context(
    row: dict[str, str],
) -> dict[str, str]:
    fastest = _number(row.get("fastest_string_seconds"))
    dropped = _integer(row.get("dropped_string_count")) or 0
    penalties = _number(row.get("penalty_count")) or 0
    flags: list[str] = []
    notes: list[str] = []
    if fastest is not None and fastest < 0.73:
        flags.append("REVIEW_EXTREME_FAST_STRING")
        notes.append(
            "Extremely fast string; confirm the recorded time."
        )
    elif fastest is not None and fastest < 1.20:
        flags.append("REVIEW_FAST_STRING")
        notes.append(
            "Fast string; review the score while preserving it as valid."
        )
    if dropped > 0:
        flags.append("REVIEW_DROPS")
        notes.append(
            f"{dropped} string(s) were dropped or unscored."
        )
    if penalties > 0:
        flags.append("REVIEW_PENALTY")
        notes.append(
            f"{_clean_number(penalties)} penalty count recorded."
        )
    return {
        "coach_flag": ";".join(flags),
        "coach_note": " ".join(notes),
    }


def _finding_coach_note(row: dict[str, str]) -> str:
    finding_type = row.get("finding_type", "")
    messages = {
        "missing_match_score": (
            "No final score is available yet; confirm completion status."
        ),
        "unscored_stage": (
            "This stage has no scored strings; confirm whether it is pending."
        ),
        "five_nonzero_totals": (
            "Five scored strings were present; the four fastest were used."
        ),
        "missing_athlete_name": (
            "The source entry is missing an athlete name."
        ),
        "missing_class": (
            "The source entry is missing the athlete class."
        ),
        "duplicate_athlete_discipline": (
            "Two entries share this athlete and discipline; verify both."
        ),
        "fast_string_yellow_review": (
            "Fast performance; review the string without invalidating it."
        ),
        "fast_string_red_review": (
            "Extremely fast performance; confirm the recorded string."
        ),
        "match_level_adjustment": (
            "The match total includes an adjustment beyond stage totals."
        ),
    }
    return messages.get(
        finding_type,
        row.get("message", ""),
    )


def _rows_by_athlete_name(
    rows: Iterable[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("athlete_name", "")].append(row)
    return grouped


def _best_placing(
    rows: list[dict[str, str]],
) -> dict[str, str] | None:
    if not rows:
        return None
    return min(
        rows,
        key=lambda row: (
            _integer(row.get("place")) or 10**9,
            _number(row.get("score_seconds")) or 10**9,
            row.get("rank_scope", ""),
        ),
    )


def _select(
    row: dict[str, str],
    columns: Iterable[str],
) -> dict[str, str]:
    return {
        column: row.get(column, "")
        for column in columns
    }


def _first_value(
    rows: list[dict[str, str]],
    column: str,
) -> str:
    return next(
        (
            row.get(column, "")
            for row in rows
            if row.get(column)
        ),
        "",
    )


def _severity_count(
    rows: list[dict[str, str]],
    severity: str,
) -> int:
    return sum(
        row.get("severity") == severity
        for row in rows
    )


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


def _truthy(value: Any) -> bool:
    return str(value).strip().casefold() == "true"


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
            raise TeamReportError(
                f"Input tables contain unexpected match IDs: "
                f"{sorted(unexpected)}"
            )


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            return list(csv.DictReader(source))
    except FileNotFoundError as exc:
        raise TeamReportError(f"Missing team report input: {path}") from exc
    except (OSError, csv.Error) as exc:
        raise TeamReportError(
            f"Could not read team report input {path}: {exc}"
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
        raise TeamReportError(
            f"Could not write team report table {path}: {exc}"
        ) from exc


def _ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise TeamReportError(
            f"Could not create team report directory {path}: {exc}"
        ) from exc
