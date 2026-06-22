"""Build the curated Wilco analysis workbook from local report outputs."""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from wilco_as_reporting.athlete_aliases import (
    AthleteAliasError,
    apply_athlete_aliases,
    load_athlete_aliases,
)
from wilco_as_reporting.team_profiles import TeamProfile

PLACEHOLDER_ID = "9999"
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True)
LABEL_FILL = PatternFill("solid", fgColor="D9EAF7")

SHEETS = (
    (
        "Wilco Match Score History",
        "wilco_match_score_history.csv",
        (
            "match_id", "match_name", "match_date", "season_label",
            "athlete_name", "athlete_id", "division", "class", "gender",
            "discipline", "match_score", "overall_place", "gender_place",
            "division_place", "class_place", "squad_place", "rank_scope",
            "award_scope", "data_status", "notes",
        ),
    ),
    (
        "Athlete Perf by Discipline",
        "athlete_performance_by_discipline.csv",
        (
            "athlete_name", "athlete_id", "discipline",
            "number_of_matches", "scored_matches_count", "best_score",
            "match_with_best_score", "best_score_date", "most_recent_score",
            "most_recent_match", "most_recent_date", "avg_score",
            "median_score", "personal_record_score", "seconds_from_pr",
            "trend_note", "confidence_level",
        ),
    ),
    (
        "All Teams by Match & Disc",
        "all_teams_by_match_and_discipline.csv",
        (
            "match_id", "match_name", "match_date", "discipline",
            "team_name", "team_id", "athlete_count", "entry_count",
            "avg_score", "median_score", "best_score", "top_4_average",
            "squad_count", "is_wilco", "notes",
        ),
    ),
    (
        "Published SASP Rankings",
        "published_sasp_rankings.csv",
        (
            "match_id", "match_name", "match_date", "discipline",
            "athlete_name", "athlete_id", "score", "rank_type",
            "rank_scope", "place", "field_size", "percentile",
            "margin_to_leader", "margin_to_previous_place",
            "margin_to_podium_cutoff", "team_name", "athlete_class",
            "gender", "squad_name", "source_file",
        ),
    ),
    (
        "Athlete Capability Matrix",
        "athlete_capability_matrix.csv",
        (),
    ),
    (
        "Athlete Discipline Stage Values",
        "athlete_discipline_stage_values.csv",
        (
            "athlete_name", "athlete_id", "discipline", "stage_name",
            "season_label", "match_id", "match_name", "avg_string",
            "fastest_string", "avg_stage", "fastest_stage",
            "match_score", "notes",
        ),
    ),
    (
        "Wilco vs Field by Discipline",
        "wilco_vs_field_by_discipline.csv",
        (
            "discipline", "wilco_entries", "field_entries", "wilco_avg",
            "field_avg", "wilco_best", "field_best", "top_team_avg",
            "avg_gap_to_field", "best_gap_to_field", "trend_note",
        ),
    ),
    (
        "Match Results",
        "match_results.csv",
        (
            "match_id", "match_name", "match_date", "athlete_name",
            "athlete_id", "discipline", "division", "class", "gender",
            "match_score", "current_rank", "rank_scope", "award_scope",
            "field_size", "notes",
        ),
    ),
    (
        "Wilco Stage Review",
        "match_review_wilco_stage_scores.csv",
        (
            "match_id", "match_name", "athlete_name", "athlete_id",
            "discipline", "stage_name", "stage_score", "fastest_string",
            "avg_string", "string_count", "match_total", "current_rank",
            "rank_scope", "notes",
        ),
    ),
    (
        "National Staff Validation",
        "match_review_national_staff_validation.csv",
        (
            "match_id", "match_name", "severity", "finding_type",
            "athlete_name", "team_name", "discipline", "stage_name",
            "score", "expected_score", "difference", "finding_message",
            "recommended_review", "notes",
        ),
    ),
    (
        "Records and PRs",
        "records_and_prs.csv",
        (
            "record_type", "athlete_name", "discipline", "score",
            "match_name", "match_date", "season_label", "previous_score",
            "improvement_seconds", "display_eligible",
            "confidence_level", "notes",
        ),
    ),
    (
        "Selected Match Highlights",
        "selected_match_record_highlights.csv",
        (
            "match_id", "match_name", "match_date", "athlete_name",
            "discipline", "highlight_type", "score",
            "previous_record_or_pr", "improvement_seconds",
            "record_scope", "display_eligible", "notes",
        ),
    ),
    (
        "Data Quality Notes",
        "data_quality_notes.csv",
        ("area", "issue_type", "affected_rows", "severity", "notes"),
    ),
)

SECONDS_COLUMNS = {
    "match_score", "score", "best_score", "most_recent_score", "avg_score",
    "median_score", "personal_record_score", "seconds_from_pr",
    "avg_string", "fastest_string", "avg_stage", "fastest_stage",
    "wilco_avg", "field_avg", "wilco_best", "field_best", "top_team_avg",
    "avg_gap_to_field", "best_gap_to_field", "stage_score", "match_total",
    "expected_score", "difference", "previous_score",
    "improvement_seconds", "previous_record_or_pr",
}


class AnalysisWorkbookError(RuntimeError):
    """Raised when local analysis inputs cannot be composed."""


@dataclass(frozen=True)
class AnalysisWorkbookResult:
    workbook_path: Path
    tables_dir: Path
    selected_match_id: int
    selected_match_name: str
    sheet_names: tuple[str, ...]
    row_counts: dict[str, int]
    chart_included: bool
    no_score_selected_match: bool


def build_analysis_workbook(
    *,
    output_root: Path | str,
    profile: TeamProfile,
    match_id: int | None = None,
    history_dir: Path | str | None = None,
    records_dir: Path | str | None = None,
    nationals_readiness_dir: Path | str | None = None,
    past_seasons: int = 2,
    workbook_name: str | None = None,
    include_all_teams: bool = True,
    include_validation: bool = True,
) -> AnalysisWorkbookResult:
    """Build the analysis tables and workbook without making API calls."""
    root = Path(output_root)
    history = Path(history_dir) if history_dir else root / "history"
    records = Path(records_dir) if records_dir else root / "records"
    readiness = (
        Path(nationals_readiness_dir)
        if nationals_readiness_dir
        else root / "nationals_readiness"
    )
    source_rows = _read_required(history / "history_source_matches.csv")
    participation = _read_required(history / "wilco_match_participation.csv")
    try:
        aliases = load_athlete_aliases()
    except AthleteAliasError as exc:
        raise AnalysisWorkbookError(str(exc)) from exc

    participation = apply_athlete_aliases(
        [row for row in participation if not _is_placeholder(row)],
        aliases,
    )
    selected_id = match_id or _latest_scored_match(participation)
    source_by_id = {row["match_id"]: row for row in source_rows}
    selected_source = source_by_id.get(str(selected_id), {})
    selected_scores_path = root / str(selected_id) / "tables" / "match_scores.csv"
    selected_scores = _read_required(selected_scores_path)
    selected_scores = apply_athlete_aliases(selected_scores, aliases)
    selected_name = (
        selected_source.get("match_name")
        or _first(selected_scores, "match_name")
        or f"Match {selected_id}"
    )
    selected_date = selected_source.get("match_date", "")

    cutoff_date = selected_date or datetime.now(timezone.utc).date().isoformat()
    seasons = _selected_seasons(source_rows, past_seasons, cutoff_date)
    scoped_sources = [
        row for row in source_rows
        if row.get("season_label") in seasons
        and (
            not row.get("match_date")
            or row.get("match_date", "") <= cutoff_date
        )
    ]
    scoped_ids = {row["match_id"] for row in scoped_sources}
    scoped_participation = [
        row for row in participation if row.get("match_id") in scoped_ids
    ]
    source_lookup = {row["match_id"]: row for row in scoped_sources}

    rankings = _load_rankings(root, scoped_ids, source_lookup, aliases)
    ranking_index = _ranking_index(rankings)
    squad_index = _load_squad_places(root, scoped_ids)
    match_history = _match_history_rows(
        scoped_participation, ranking_index, squad_index
    )
    athlete_performance = _athlete_performance_rows(
        scoped_participation,
        _read_optional(records / "personal_records.csv"),
    )
    all_scores = _load_all_scores(root, scoped_ids, aliases)
    all_teams = _all_team_rows(
        all_scores, source_lookup, profile, include_all_teams
    )
    stage_values = _stage_value_rows(
        root, scoped_ids, source_lookup, profile, aliases,
        scoped_participation,
    )
    capability_columns, capability = _capability_rows(stage_values)
    field_comparison = _field_comparison_rows(all_scores, profile)
    match_results = _selected_match_rows(
        selected_id, selected_name, selected_date, selected_scores,
        profile, ranking_index,
    )
    stage_review = _selected_stage_rows(
        root, selected_id, selected_name, selected_scores, profile,
        ranking_index, aliases,
    )
    validation = _validation_rows(
        root, selected_id, selected_name, include_validation
    )
    records_rows = _records_rows(records, seasons)
    highlights = _highlight_rows(
        records, selected_id, selected_name, selected_date
    )
    no_score = not any(_number(row.get("match_score_seconds"))
                       for row in selected_scores
                       if profile.matches_name(row.get("team_name")))
    quality = _quality_rows(
        source_rows=scoped_sources,
        selected_match_id=selected_id,
        selected_no_score=no_score,
        selected_scores=selected_scores,
        profile=profile,
        participation=participation,
        aliases_applied=sum(
            row.get("original_athlete_name", "") != row.get("athlete_name", "")
            for row in participation
        ),
        validation_rows=validation,
        readiness_dir=readiness,
    )
    rows_by_filename: dict[str, list[dict[str, Any]]] = {
        "wilco_match_score_history.csv": match_history,
        "athlete_performance_by_discipline.csv": athlete_performance,
        "all_teams_by_match_and_discipline.csv": all_teams,
        "published_sasp_rankings.csv": rankings,
        "athlete_capability_matrix.csv": capability,
        "athlete_discipline_stage_values.csv": stage_values,
        "wilco_vs_field_by_discipline.csv": field_comparison,
        "match_results.csv": match_results,
        "match_review_wilco_stage_scores.csv": stage_review,
        "match_review_national_staff_validation.csv": validation,
        "records_and_prs.csv": records_rows,
        "selected_match_record_highlights.csv": highlights,
        "data_quality_notes.csv": quality,
    }
    columns_by_filename = {
        filename: tuple(columns)
        for _, filename, columns in SHEETS
    }
    columns_by_filename["athlete_capability_matrix.csv"] = capability_columns

    analysis_dir = root / "analysis"
    tables_dir = analysis_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for filename, rows in rows_by_filename.items():
        _write_csv(tables_dir / filename, columns_by_filename[filename], rows)

    workbook_path = analysis_dir / (
        workbook_name or "wilco_analysis_workbook.xlsx"
    )
    if workbook_path.suffix.casefold() != ".xlsx":
        workbook_path = workbook_path.with_suffix(".xlsx")
    cover = {
        "workbook_name": workbook_path.stem.replace("_", " ").title(),
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0).isoformat(),
        "team_key": profile.team_key,
        "selected_match_id": selected_id,
        "selected_match_name": selected_name,
        "selected_match_date": selected_date,
        "seasons_included": ", ".join(seasons),
        "source_matches_count": len(scoped_sources),
        "athletes_count": len({
            (row.get("athlete_name"), row.get("athlete_id"))
            for row in scoped_participation
        }),
        "disciplines_count": len({
            row.get("discipline") for row in scoped_participation
        }),
        "notes": (
            "Lower times are better. Stage and string values are capability "
            "benchmarks, not formal records. Long requested sheet names are "
            "abbreviated to comply with Excel's 31-character limit."
        ),
    }
    chart_included = _write_workbook(
        workbook_path, cover, rows_by_filename, columns_by_filename
    )
    return AnalysisWorkbookResult(
        workbook_path=workbook_path,
        tables_dir=tables_dir,
        selected_match_id=selected_id,
        selected_match_name=selected_name,
        sheet_names=("Cover", *(sheet for sheet, _, _ in SHEETS)),
        row_counts={
            filename: len(rows) for filename, rows in rows_by_filename.items()
        },
        chart_included=chart_included,
        no_score_selected_match=no_score,
    )


def _match_history_rows(
    rows: list[dict[str, Any]],
    rankings: dict[tuple[str, str, str], list[dict[str, Any]]],
    squads: dict[tuple[str, str, str], str],
) -> list[dict[str, Any]]:
    results = []
    for row in rows:
        key = (row["match_id"], row["athlete_name"], row["discipline"])
        rank_rows = rankings.get(key, [])
        preferred = _preferred_ranking(rank_rows)
        results.append({
            "match_id": row["match_id"],
            "match_name": row["match_name"],
            "match_date": row["match_date"],
            "season_label": row["season_label"],
            "athlete_name": row["athlete_name"],
            "athlete_id": row["athlete_id"],
            "division": row.get("division", ""),
            "class": row.get("class", ""),
            "gender": row.get("gender", ""),
            "discipline": row["discipline"],
            "match_score": row.get("score", ""),
            "overall_place": _place_for(rank_rows, "all"),
            "gender_place": _place_for(rank_rows, "gender"),
            "division_place": _place_for(rank_rows, "division"),
            "class_place": _place_for(rank_rows, "class"),
            "squad_place": squads.get(key, ""),
            "rank_scope": preferred.get("rank_scope", ""),
            "award_scope": preferred.get("award_scope", ""),
            "data_status": row.get("data_status", ""),
            "notes": row.get("notes", ""),
        })
    return sorted(results, key=_history_sort)


def _athlete_performance_rows(
    participation: list[dict[str, Any]],
    personal_records: list[dict[str, str]],
) -> list[dict[str, Any]]:
    pr_index = {
        (row.get("athlete_id", ""), row.get("discipline", "")): row
        for row in personal_records
    }
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in participation:
        grouped[(row["athlete_name"], row["athlete_id"],
                 row["discipline"])].append(row)
    results = []
    for key, rows in grouped.items():
        scored = [row for row in rows if _number(row.get("score")) is not None]
        ordered = sorted(rows, key=lambda row: (
            row.get("match_date", ""), _integer(row.get("match_id"))
        ))
        latest = ordered[-1]
        scores = [_number(row["score"]) for row in scored]
        numeric = [score for score in scores if score is not None]
        best = min(scored, key=lambda row: _number(row["score"]) or 999999) \
            if scored else {}
        pr = pr_index.get((key[1], key[2]), {})
        latest_score = _number(latest.get("score"))
        pr_score = _number(pr.get("personal_record_score"))
        results.append({
            "athlete_name": key[0], "athlete_id": key[1],
            "discipline": key[2],
            "number_of_matches": len({row["match_id"] for row in rows}),
            "scored_matches_count": len(scored),
            "best_score": _display(min(numeric) if numeric else None),
            "match_with_best_score": best.get("match_name", ""),
            "best_score_date": best.get("match_date", ""),
            "most_recent_score": _display(latest_score),
            "most_recent_match": latest.get("match_name", ""),
            "most_recent_date": latest.get("match_date", ""),
            "avg_score": _display(statistics.mean(numeric) if numeric else None),
            "median_score": _display(
                statistics.median(numeric) if numeric else None
            ),
            "personal_record_score": _display(pr_score),
            "seconds_from_pr": _display(
                latest_score - pr_score
                if latest_score is not None and pr_score is not None else None
            ),
            "trend_note": _trend_note(scored),
            "confidence_level": _confidence(len(scored)),
        })
    return sorted(results, key=lambda row: (
        row["athlete_name"], row["discipline"]
    ))


def _all_team_rows(
    scores: list[dict[str, Any]],
    sources: dict[str, dict[str, str]],
    profile: TeamProfile,
    include_all: bool,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in scores:
        if not include_all and not profile.matches_name(row.get("team_name")):
            continue
        grouped[(row["match_id"], row["discipline"],
                 row.get("team_name", ""))].append(row)
    results = []
    for key, rows in grouped.items():
        values = sorted(
            value for value in (_number(row.get("match_score_seconds"))
                                for row in rows) if value is not None
        )
        if not values:
            continue
        source = sources.get(key[0], {})
        results.append({
            "match_id": key[0],
            "match_name": source.get("match_name")
            or rows[0].get("match_name", ""),
            "match_date": source.get("match_date", ""),
            "discipline": key[1], "team_name": key[2], "team_id": "",
            "athlete_count": len({
                (row.get("athlete_id"), row.get("athlete_name"))
                for row in rows if row.get("athlete_name")
            }),
            "entry_count": len(values),
            "avg_score": _display(statistics.mean(values)),
            "median_score": _display(statistics.median(values)),
            "best_score": _display(min(values)),
            "top_4_average": _display(statistics.mean(values[:4])),
            "squad_count": "",
            "is_wilco": _boolean(profile.matches_name(key[2])),
            "notes": "Team ID and squad count are unavailable in match scores.",
        })
    return sorted(results, key=lambda row: (
        row["match_date"], row["match_id"], row["discipline"],
        row["team_name"]
    ))


def _stage_value_rows(
    root: Path,
    match_ids: set[str],
    sources: dict[str, dict[str, str]],
    profile: TeamProfile,
    aliases: tuple[Any, ...],
    participation: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    score_index = {
        (row["match_id"], row["athlete_id"], row["discipline"]):
        row.get("score", "") for row in participation
    }
    results = []
    for match_id in sorted(match_ids, key=_integer):
        path = root / match_id / "tables" / "stage_scores.csv"
        rows = apply_athlete_aliases(_read_optional(path), aliases)
        source = sources.get(match_id, {})
        for row in rows:
            if not profile.matches_name(row.get("team_name")) \
                    or _is_placeholder(row):
                continue
            stage_score = _number(row.get("stage_score_seconds"))
            avg_string = _number(row.get("scored_avg_string_seconds"))
            fastest = _number(row.get("fastest_string_seconds"))
            if stage_score is None and avg_string is None and fastest is None:
                continue
            results.append({
                "athlete_name": row.get("athlete_name", ""),
                "athlete_id": row.get("athlete_id", ""),
                "discipline": row.get("discipline", ""),
                "stage_name": row.get("stage_name", ""),
                "season_label": source.get("season_label", ""),
                "match_id": match_id,
                "match_name": source.get("match_name")
                or row.get("match_name", ""),
                "avg_string": _display(avg_string),
                "fastest_string": _display(fastest),
                "avg_stage": _display(stage_score),
                "fastest_stage": _display(stage_score),
                "match_score": score_index.get((
                    match_id, row.get("athlete_id", ""),
                    row.get("discipline", "")
                ), ""),
                "notes": (
                    "Stage and string values are capability benchmarks only."
                ),
            })
    return sorted(results, key=lambda row: (
        row["athlete_name"], row["discipline"], row["stage_name"],
        row["season_label"], row["match_id"]
    ))


def _capability_rows(
    values: list[dict[str, Any]],
) -> tuple[tuple[str, ...], list[dict[str, Any]]]:
    stages = sorted({row["stage_name"] for row in values if row["stage_name"]})
    columns = ["athlete_name", "athlete_id", "discipline"]
    for stage in stages:
        columns.extend((
            f"{stage} Avg String", f"{stage} Fastest String",
            f"{stage} Avg Stage", f"{stage} Fastest Stage",
        ))
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in values:
        grouped[(row["athlete_name"], row["athlete_id"],
                 row["discipline"])].append(row)
    results = []
    for key, rows in grouped.items():
        result: dict[str, Any] = {
            "athlete_name": key[0], "athlete_id": key[1],
            "discipline": key[2],
        }
        for stage in stages:
            stage_rows = [row for row in rows if row["stage_name"] == stage]
            strings = [_number(row["avg_string"]) for row in stage_rows]
            fast_strings = [_number(row["fastest_string"]) for row in stage_rows]
            stage_scores = [_number(row["avg_stage"]) for row in stage_rows]
            strings = [value for value in strings if value is not None]
            fast_strings = [value for value in fast_strings if value is not None]
            stage_scores = [value for value in stage_scores if value is not None]
            result[f"{stage} Avg String"] = _display(
                statistics.mean(strings) if strings else None
            )
            result[f"{stage} Fastest String"] = _display(
                min(fast_strings) if fast_strings else None
            )
            result[f"{stage} Avg Stage"] = _display(
                statistics.mean(stage_scores) if stage_scores else None
            )
            result[f"{stage} Fastest Stage"] = _display(
                min(stage_scores) if stage_scores else None
            )
        results.append(result)
    return tuple(columns), sorted(results, key=lambda row: (
        row["athlete_name"], row["discipline"]
    ))


def _field_comparison_rows(
    scores: list[dict[str, Any]], profile: TeamProfile
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scores:
        if _number(row.get("match_score_seconds")) is not None:
            grouped[row["discipline"]].append(row)
    results = []
    for discipline, rows in grouped.items():
        wilco = [_number(row["match_score_seconds"]) for row in rows
                 if profile.matches_name(row.get("team_name"))]
        field = [_number(row["match_score_seconds"]) for row in rows
                 if not profile.matches_name(row.get("team_name"))]
        wilco_values = [value for value in wilco if value is not None]
        field_values = [value for value in field if value is not None]
        if not wilco_values:
            continue
        team_values: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            value = _number(row["match_score_seconds"])
            if value is not None:
                team_values[row.get("team_name", "")].append(value)
        top_team = min(
            (statistics.mean(sorted(values)[:4])
             for values in team_values.values() if values),
            default=None,
        )
        wilco_avg = statistics.mean(wilco_values)
        field_avg = statistics.mean(field_values) if field_values else None
        wilco_best = min(wilco_values)
        field_best = min(field_values) if field_values else None
        avg_gap = wilco_avg - field_avg if field_avg is not None else None
        best_gap = wilco_best - field_best if field_best is not None else None
        results.append({
            "discipline": discipline, "wilco_entries": len(wilco_values),
            "field_entries": len(field_values),
            "wilco_avg": _display(wilco_avg),
            "field_avg": _display(field_avg),
            "wilco_best": _display(wilco_best),
            "field_best": _display(field_best),
            "top_team_avg": _display(top_team),
            "avg_gap_to_field": _display(avg_gap),
            "best_gap_to_field": _display(best_gap),
            "trend_note": (
                "Negative gaps mean Wilco is faster/better than the field. "
                + ("Wilco average is faster." if avg_gap is not None
                   and avg_gap < 0 else "Wilco average trails the field."
                   if avg_gap is not None else "Field comparison unavailable.")
            ),
        })
    return sorted(results, key=lambda row: row["discipline"])


def _selected_match_rows(
    match_id: int, match_name: str, match_date: str,
    scores: list[dict[str, Any]], profile: TeamProfile,
    rankings: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    results = []
    for row in scores:
        if not profile.matches_name(row.get("team_name")) \
                or _is_placeholder(row):
            continue
        key = (str(match_id), row["athlete_name"], row["discipline"])
        preferred = _preferred_ranking(rankings.get(key, []))
        score = _number(row.get("match_score_seconds"))
        results.append({
            "match_id": match_id, "match_name": match_name,
            "match_date": match_date, "athlete_name": row["athlete_name"],
            "athlete_id": row["athlete_id"],
            "discipline": row["discipline"],
            "division": _division(row.get("class", "")),
            "class": row.get("class", ""), "gender": row.get("gender", ""),
            "match_score": _display(score),
            "current_rank": preferred.get("place", ""),
            "rank_scope": preferred.get("rank_scope", ""),
            "award_scope": preferred.get("award_scope", ""),
            "field_size": preferred.get("field_size", ""),
            "notes": (
                "No scored result is currently available."
                if score is None else ""
            ),
        })
    return sorted(results, key=lambda row: (
        row["athlete_name"], row["discipline"]
    ))


def _selected_stage_rows(
    root: Path, match_id: int, match_name: str,
    scores: list[dict[str, Any]], profile: TeamProfile,
    rankings: dict[tuple[str, str, str], list[dict[str, Any]]],
    aliases: tuple[Any, ...],
) -> list[dict[str, Any]]:
    score_index = {
        (row["athlete_id"], row["discipline"]):
        row.get("match_score_seconds", "") for row in scores
    }
    rows = apply_athlete_aliases(_read_optional(
        root / str(match_id) / "tables" / "stage_scores.csv"
    ), aliases)
    results = []
    for row in rows:
        if not profile.matches_name(row.get("team_name")) \
                or _is_placeholder(row):
            continue
        key = (str(match_id), row["athlete_name"], row["discipline"])
        preferred = _preferred_ranking(rankings.get(key, []))
        stage_score = _number(row.get("stage_score_seconds"))
        results.append({
            "match_id": match_id, "match_name": match_name,
            "athlete_name": row["athlete_name"],
            "athlete_id": row["athlete_id"],
            "discipline": row["discipline"],
            "stage_name": row.get("stage_name", ""),
            "stage_score": _display(stage_score),
            "fastest_string": _display(
                _number(row.get("fastest_string_seconds"))
            ),
            "avg_string": _display(
                _number(row.get("scored_avg_string_seconds"))
            ),
            "string_count": 4 if stage_score is not None else 0,
            "match_total": score_index.get((
                row["athlete_id"], row["discipline"]
            ), ""),
            "current_rank": preferred.get("place", ""),
            "rank_scope": preferred.get("rank_scope", ""),
            "notes": (
                "Unscored stage; retained as entry context."
                if stage_score is None else
                "Capability detail only; not a formal stage record."
            ),
        })
    return sorted(results, key=lambda row: (
        row["athlete_name"], row["discipline"], row["stage_name"]
    ))


def _validation_rows(
    root: Path, match_id: int, match_name: str, include: bool
) -> list[dict[str, Any]]:
    if not include:
        return []
    findings = _read_optional(
        root / str(match_id) / "validation" / "validation_findings.csv"
    )
    results = []
    for row in findings:
        severity = row.get("severity", "")
        results.append({
            "match_id": match_id, "match_name": match_name,
            "severity": severity, "finding_type": row.get("finding_type", ""),
            "athlete_name": row.get("athlete_name", ""),
            "team_name": row.get("team_name", ""),
            "discipline": row.get("discipline", ""),
            "stage_name": row.get("stage_name", ""),
            "score": row.get("actual_value", ""),
            "expected_score": row.get("expected_value", ""),
            "difference": row.get("difference", ""),
            "finding_message": row.get("message", ""),
            "recommended_review": (
                "Correct source or parser mismatch."
                if severity == "ERROR" else
                "Coach or match staff should review context."
                if severity in {"WARNING", "REVIEW"} else
                "Context only."
            ),
            "notes": (
                "Review findings are not automatically invalid scores."
            ),
        })
    return results


def _records_rows(records: Path, seasons: tuple[str, ...]) -> list[dict[str, Any]]:
    results = []
    for row in _read_optional(records / "personal_records.csv"):
        if row.get("personal_record_season_label") not in seasons:
            continue
        results.append({
            "record_type": "personal_record",
            "athlete_name": row.get("athlete_name", ""),
            "discipline": row.get("discipline", ""),
            "score": row.get("personal_record_score", ""),
            "match_name": row.get("personal_record_match_name", ""),
            "match_date": row.get("personal_record_match_date", ""),
            "season_label": row.get("personal_record_season_label", ""),
            "previous_score": "", "improvement_seconds": "",
            "display_eligible": row.get("display_eligible", ""),
            "confidence_level": row.get("confidence_level", ""),
            "notes": row.get("notes", ""),
        })
    for filename, record_type in (
        ("wilco_all_time_records.csv", "wilco_all_time_record"),
        ("wilco_team_season_records.csv", "team_season_record"),
    ):
        for row in _read_optional(records / filename):
            if record_type == "team_season_record" \
                    and row.get("season_label") not in seasons:
                continue
            results.append({
                "record_type": record_type,
                "athlete_name": row.get("athlete_name", ""),
                "discipline": row.get("discipline", ""),
                "score": row.get("score", ""),
                "match_name": row.get("match_name", ""),
                "match_date": row.get("match_date", ""),
                "season_label": row.get("season_label", ""),
                "previous_score": "", "improvement_seconds": "",
                "display_eligible": "true",
                "confidence_level": row.get("confidence_level", ""),
                "notes": row.get("notes", ""),
            })
    for row in _read_optional(records / "recent_pr_highlights.csv"):
        if row.get("season_label") not in seasons:
            continue
        results.append({
            "record_type": "recent_pr_highlight",
            "athlete_name": row.get("athlete_name", ""),
            "discipline": row.get("discipline", ""),
            "score": row.get("new_pr_score", ""),
            "match_name": row.get("match_name", ""),
            "match_date": row.get("match_date", ""),
            "season_label": row.get("season_label", ""),
            "previous_score": row.get("previous_pr_score", ""),
            "improvement_seconds": row.get("improvement_seconds", ""),
            "display_eligible": row.get("display_eligible", ""),
            "confidence_level": row.get("confidence_level", ""),
            "notes": row.get("display_note", ""),
        })
    return sorted(results, key=lambda row: (
        row["record_type"], row["discipline"], row["athlete_name"]
    ))


def _highlight_rows(
    records: Path, match_id: int, match_name: str, match_date: str
) -> list[dict[str, Any]]:
    results = []
    for row in _read_optional(records / "new_personal_records_by_match.csv"):
        if _integer(row.get("match_id")) != match_id:
            continue
        results.append({
            "match_id": match_id, "match_name": match_name,
            "match_date": match_date, "athlete_name": row["athlete_name"],
            "discipline": row["discipline"],
            "highlight_type": row.get("pr_event_type", "new_personal_record"),
            "score": row.get("new_pr_score", ""),
            "previous_record_or_pr": row.get("previous_pr_score", ""),
            "improvement_seconds": row.get("improvement_seconds", ""),
            "record_scope": "personal_record",
            "display_eligible": "true",
            "notes": row.get("notes", ""),
        })
    for row in _read_optional(records / "match_bests.csv"):
        if _integer(row.get("match_id")) != match_id:
            continue
        results.append({
            "match_id": match_id, "match_name": match_name,
            "match_date": match_date, "athlete_name": row["athlete_name"],
            "discipline": row["discipline"], "highlight_type": "match_best",
            "score": row.get("score", ""), "previous_record_or_pr": "",
            "improvement_seconds": "",
            "record_scope": row.get("match_best_scope", ""),
            "display_eligible": "true", "notes": row.get("notes", ""),
        })
    return sorted(results, key=lambda row: (
        row["discipline"], row["highlight_type"], row["athlete_name"]
    ))


def _quality_rows(
    *, source_rows: list[dict[str, str]], selected_match_id: int,
    selected_no_score: bool, selected_scores: list[dict[str, Any]],
    profile: TeamProfile,
    participation: list[dict[str, Any]], aliases_applied: int,
    validation_rows: list[dict[str, Any]], readiness_dir: Path,
) -> list[dict[str, Any]]:
    partial = sum(row.get("data_status") == "partial" for row in source_rows)
    selected_team_scores = [
        row for row in selected_scores
        if profile.matches_name(row.get("team_name"))
    ]
    placeholders = sum(_is_placeholder(row) for row in selected_team_scores)
    ranking_gaps = sum(
        "No preferred individual ranking" in row.get("notes", "")
        for row in participation if row.get("match_id") == str(selected_match_id)
    )
    schedule_missing = sum(
        not (readiness_dir.parent / row["match_id"] / "raw"
             / f"{row['match_id']}_schedule.json").exists()
        for row in source_rows
    )
    rows = [
        {
            "area": "selected_match", "issue_type": "no_scores",
            "affected_rows": sum(
                _number(row.get("match_score_seconds")) is None
                for row in selected_team_scores
            ) if selected_no_score else 0,
            "severity": "INFO",
            "notes": (
                "Selected match has entries but no current Wilco scores; "
                "score-dependent cells remain blank."
                if selected_no_score else "Selected match has scored results."
            ),
        },
        {
            "area": "history", "issue_type": "partial_matches",
            "affected_rows": partial, "severity": "REVIEW",
            "notes": "Partial matches remain visible with data-status context.",
        },
        {
            "area": "raw_metadata", "issue_type": "missing_schedules",
            "affected_rows": schedule_missing, "severity": "INFO",
            "notes": "Schedule metadata is optional and does not block analysis.",
        },
        {
            "area": "raw_data", "issue_type": "empty_slot_matches_excluded",
            "affected_rows": sum(
                row.get("core_complete") != "true" for row in source_rows
            ), "severity": "INFO",
            "notes": "Matches without useful core JSON are not analyzed.",
        },
        {
            "area": "identity", "issue_type": "placeholder_rows_excluded",
            "affected_rows": placeholders, "severity": "WARNING",
            "notes": "Blank athlete names and athlete ID 9999 are excluded.",
        },
        {
            "area": "identity", "issue_type": "alias_mappings_applied",
            "affected_rows": aliases_applied, "severity": "INFO",
            "notes": "Configured athlete aliases were canonicalized.",
        },
        {
            "area": "rankings", "issue_type": "ranking_gaps",
            "affected_rows": ranking_gaps, "severity": "INFO",
            "notes": "Some entries do not have a matching published ranking.",
        },
        {
            "area": "validation", "issue_type": "validation_limitations",
            "affected_rows": len(validation_rows), "severity": "INFO",
            "notes": (
                "Validation findings are review aids; explainable findings "
                "are not automatically scoring errors."
            ),
        },
    ]
    return rows


def _load_rankings(
    root: Path, match_ids: set[str],
    sources: dict[str, dict[str, str]], aliases: tuple[Any, ...],
) -> list[dict[str, Any]]:
    results = []
    for match_id in sorted(match_ids, key=_integer):
        path = root / match_id / "tables" / "rankings.csv"
        rows = apply_athlete_aliases(_read_optional(path), aliases)
        source = sources.get(match_id, {})
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if not row.get("athlete_name") or _is_placeholder(row):
                continue
            grouped[(row.get("discipline", ""), row.get("leaderboard_name", ""),
                     row.get("rank_scope", ""))].append(row)
        for row in rows:
            if not row.get("athlete_name") or _is_placeholder(row):
                continue
            group = grouped[(row.get("discipline", ""),
                             row.get("leaderboard_name", ""),
                             row.get("rank_scope", ""))]
            podium = next(
                (_number(item.get("score_seconds")) for item in group
                 if _integer(item.get("place")) == 3), None
            )
            score = _number(row.get("score_seconds"))
            field_size = _integer(row.get("field_size"))
            place = _integer(row.get("place"))
            results.append({
                "match_id": match_id,
                "match_name": source.get("match_name")
                or row.get("match_name", ""),
                "match_date": source.get("match_date", ""),
                "discipline": row.get("discipline", ""),
                "athlete_name": row.get("athlete_name", ""),
                "athlete_id": row.get("athlete_id", ""),
                "score": _display(score),
                "rank_type": row.get("rank_type", ""),
                "rank_scope": row.get("rank_scope", ""),
                "place": place or "",
                "field_size": field_size or "",
                "percentile": _display(
                    100 * (field_size - place + 1) / field_size
                    if field_size and place else None
                ),
                "margin_to_leader": row.get("margin_to_leader", ""),
                "margin_to_previous_place":
                    row.get("margin_to_previous_place", ""),
                "margin_to_podium_cutoff": _display(
                    score - podium if score is not None and podium is not None
                    else None
                ),
                "team_name": row.get("team_name", ""),
                "athlete_class": row.get("class", ""),
                "gender": row.get("gender_context", ""),
                "squad_name": "",
                "source_file": str(path),
                "_award_scope": row.get("award_scope", ""),
            })
    return sorted(results, key=lambda row: (
        row["match_date"], row["match_id"], row["discipline"],
        row["rank_scope"], _integer(row["place"])
    ))


def _ranking_index(
    rankings: list[dict[str, Any]],
) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    result: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rankings:
        row["award_scope"] = row.pop("_award_scope", "")
        result[(str(row["match_id"]), row["athlete_name"],
                row["discipline"])].append(row)
    return result


def _load_squad_places(
    root: Path, match_ids: set[str]
) -> dict[tuple[str, str, str], str]:
    result = {}
    for match_id in match_ids:
        for row in _read_optional(
            root / match_id / "tables" / "squad_results.csv"
        ):
            for number in range(1, 5):
                name = row.get(f"athlete_{number}_name", "")
                if name:
                    result[(match_id, name, row.get("discipline", ""))] = (
                        row.get("squad_place", "")
                    )
    return result


def _load_all_scores(
    root: Path, match_ids: set[str], aliases: tuple[Any, ...]
) -> list[dict[str, Any]]:
    results = []
    for match_id in sorted(match_ids, key=_integer):
        rows = apply_athlete_aliases(_read_optional(
            root / match_id / "tables" / "match_scores.csv"
        ), aliases)
        results.extend(row for row in rows if not _is_placeholder(row))
    return results


def _selected_seasons(
    source_rows: list[dict[str, str]], count: int, cutoff_date: str
) -> tuple[str, ...]:
    if count < 1:
        raise AnalysisWorkbookError("--past-seasons must be at least 1.")
    pairs = sorted({
        (row.get("match_date", ""), row.get("season_label", ""))
        for row in source_rows
        if row.get("match_date") and row.get("season_label")
        and row.get("match_date", "") <= cutoff_date
        and row.get("season_label") != "Unknown Season"
    }, reverse=True)
    seasons = []
    for _, season in pairs:
        if season not in seasons:
            seasons.append(season)
        if len(seasons) == count:
            break
    if not seasons:
        raise AnalysisWorkbookError("No dated seasons are available.")
    return tuple(seasons)


def _latest_scored_match(participation: list[dict[str, Any]]) -> int:
    scored = [row for row in participation if _number(row.get("score")) is not None]
    if not scored:
        raise AnalysisWorkbookError("No scored Wilco match is available.")
    return _integer(max(scored, key=lambda row: (
        row.get("match_date", ""), _integer(row.get("match_id"))
    ))["match_id"])


def _preferred_ranking(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return min(rows, key=lambda row: (
        0 if row.get("award_scope") not in {"", "Comparison"} else 1,
        0 if "class" in row.get("rank_scope", "").casefold() else 1,
        _integer(row.get("place")) or 999999,
    ), default={})


def _place_for(rows: list[dict[str, Any]], scope: str) -> Any:
    for row in sorted(rows, key=lambda item: _integer(item.get("place")) or 999999):
        rank_scope = row.get("rank_scope", "").casefold()
        rank_type = row.get("rank_type", "").casefold()
        if scope == "all" and (
            rank_scope == "all" or "overall" in rank_type
        ):
            return row.get("place", "")
        if scope in rank_scope or scope in rank_type:
            return row.get("place", "")
    return ""


def _write_workbook(
    path: Path, cover_values: dict[str, Any],
    rows_by_filename: dict[str, list[dict[str, Any]]],
    columns_by_filename: dict[str, tuple[str, ...]],
) -> bool:
    workbook = Workbook()
    cover = workbook.active
    cover.title = "Cover"
    cover.sheet_view.showGridLines = False
    cover["A1"] = cover_values["workbook_name"]
    cover["A1"].font = Font(size=20, bold=True, color="1F4E78")
    cover.merge_cells("A1:D1")
    for row_number, (label, value) in enumerate(cover_values.items(), 3):
        cover.cell(row_number, 1, label.replace("_", " ").title())
        cover.cell(row_number, 2, value)
        cover.cell(row_number, 1).fill = LABEL_FILL
        cover.cell(row_number, 1).font = Font(bold=True)
        cover.cell(row_number, 2).alignment = Alignment(
            wrap_text=True, vertical="top"
        )
    cover.column_dimensions["A"].width = 25
    cover.column_dimensions["B"].width = 90
    cover.freeze_panes = "A3"
    chart_included = False
    for number, (sheet_name, filename, _) in enumerate(SHEETS, 1):
        sheet = workbook.create_sheet(sheet_name)
        rows = rows_by_filename[filename]
        columns = columns_by_filename[filename]
        _write_table_sheet(sheet, rows, columns, number)
        if sheet_name == "Wilco vs Field by Discipline" and rows:
            _add_comparison_chart(sheet, columns, len(rows))
            chart_included = True
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        workbook.save(path)
    except OSError as exc:
        raise AnalysisWorkbookError(f"Could not save workbook {path}: {exc}") \
            from exc
    return chart_included


def _write_table_sheet(
    sheet: Any, rows: list[dict[str, Any]],
    columns: tuple[str, ...], number: int,
) -> None:
    sheet.sheet_view.showGridLines = False
    sheet.append([column.replace("_", " ").title() for column in columns])
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )
    for row in rows:
        sheet.append([_workbook_value(column, row.get(column, ""))
                      for column in columns])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    if rows:
        table = Table(displayName=f"AnalysisTable{number}", ref=sheet.dimensions)
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2", showRowStripes=True,
            showColumnStripes=False,
        )
        sheet.add_table(table)
    else:
        sheet["A2"] = "No rows are currently available for this view."
        sheet["A2"].font = Font(italic=True, color="666666")
    for column_number, column in enumerate(columns, 1):
        letter = get_column_letter(column_number)
        values = [sheet.cell(row, column_number).value
                  for row in range(2, sheet.max_row + 1)]
        sheet.column_dimensions[letter].width = _column_width(column, values)
        if column in SECONDS_COLUMNS or any(
            marker in column for marker in (
                " Avg String", " Fastest String",
                " Avg Stage", " Fastest Stage",
            )
        ):
            for cell in sheet[letter][1:]:
                if isinstance(cell.value, (int, float)):
                    cell.number_format = "0.000"
        if column == "percentile":
            for cell in sheet[letter][1:]:
                if isinstance(cell.value, (int, float)):
                    cell.number_format = "0.0"
        if column in {"notes", "finding_message", "recommended_review",
                      "trend_note"}:
            for cell in sheet[letter][1:]:
                cell.alignment = Alignment(wrap_text=True, vertical="top")


def _add_comparison_chart(
    sheet: Any, columns: tuple[str, ...], row_count: int
) -> None:
    category_col = columns.index("discipline") + 1
    wilco_col = columns.index("wilco_avg") + 1
    field_col = columns.index("field_avg") + 1
    chart = BarChart()
    chart.type = "bar"
    chart.style = 10
    chart.title = "Average Match Time: Wilco vs Field"
    chart.x_axis.title = "Seconds (lower is better)"
    chart.y_axis.title = "Discipline"
    chart.height = 10
    chart.width = 22
    chart.add_data(
        Reference(sheet, min_col=wilco_col, max_col=field_col,
                  min_row=1, max_row=row_count + 1),
        titles_from_data=True,
    )
    chart.set_categories(Reference(
        sheet, min_col=category_col, min_row=2, max_row=row_count + 1
    ))
    chart.legend.position = "r"
    sheet.add_chart(chart, f"M2")


def _write_csv(
    path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]
) -> None:
    try:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns,
                                    extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    except OSError as exc:
        raise AnalysisWorkbookError(f"Could not write {path}: {exc}") from exc


def _read_required(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise AnalysisWorkbookError(f"Required local input is missing: {path}")
    return _read_optional(path)


def _read_optional(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        raise AnalysisWorkbookError(f"Could not read {path}: {exc}") from exc


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _display(value: float | None) -> float | str:
    return round(value, 3) if value is not None else ""


def _boolean(value: bool) -> str:
    return "true" if value else "false"


def _is_placeholder(row: dict[str, Any]) -> bool:
    return (
        not str(row.get("athlete_name", "")).strip()
        or str(row.get("athlete_id", "")).strip() == PLACEHOLDER_ID
    )


def _division(value: str) -> str:
    return value.split("/", 1)[0].strip() if value else ""


def _first(rows: list[dict[str, Any]], column: str) -> str:
    return next((str(row.get(column, "")) for row in rows
                 if row.get(column)), "")


def _confidence(count: int) -> str:
    return "high" if count >= 4 else "medium" if count >= 2 else "low"


def _trend_note(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=lambda row: (
        row.get("match_date", ""), _integer(row.get("match_id"))
    ))
    if len(ordered) < 2:
        return "Insufficient scored history."
    first = _number(ordered[0].get("score"))
    latest = _number(ordered[-1].get("score"))
    if first is None or latest is None:
        return "Insufficient scored history."
    change = latest - first
    if abs(change) < 0.01:
        return "Stable across available scored matches."
    return (
        f"Improved by {abs(change):.3f} seconds from first to latest."
        if change < 0 else
        f"Latest is {change:.3f} seconds slower than first."
    )


def _history_sort(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("match_date", ""), _integer(row.get("match_id")),
        row.get("athlete_name", ""), row.get("discipline", ""),
    )


def _workbook_value(column: str, value: Any) -> Any:
    if value in ("true", "false"):
        return value == "true"
    if value == "":
        return None
    if column.endswith("_id") or column in {
        "match_id", "athlete_id", "team_id"
    }:
        return value
    numeric = _number(value)
    if numeric is not None and (
        column in SECONDS_COLUMNS
        or column.endswith("_count")
        or column in {"place", "field_size", "current_rank",
                      "overall_place", "gender_place", "division_place",
                      "class_place", "squad_place", "athlete_count",
                      "entry_count", "number_of_matches",
                      "scored_matches_count", "string_count",
                      "wilco_entries", "field_entries", "affected_rows",
                      "percentile"}
        or " Avg String" in column or " Fastest String" in column
        or " Avg Stage" in column or " Fastest Stage" in column
    ):
        return numeric
    return value


def _column_width(column: str, values: Iterable[Any]) -> float:
    if column in {"notes", "finding_message", "recommended_review",
                  "trend_note"}:
        return 55
    if column in {"match_name", "source_file"}:
        return 42
    if column in {"athlete_name", "team_name", "rank_scope",
                  "award_scope", "stage_name"}:
        return 24
    longest = max(
        [len(column.replace("_", " ").title())]
        + [len(str(value)) for value in values if value is not None],
    )
    return min(max(longest + 2, 10), 28)
