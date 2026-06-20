"""Parse raw SASP match snapshots into normalized base tables."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

MATCH_SCORE_COLUMNS = (
    "match_id",
    "match_name",
    "athlete_id",
    "athlete_name",
    "team_name",
    "class",
    "gender",
    "discipline_id",
    "discipline",
    "match_score_seconds",
    "dnf_flag",
    "dq_flag",
)

RANKING_COLUMNS = (
    "match_id",
    "match_name",
    "discipline_id",
    "discipline",
    "leaderboard_name",
    "leaderboard_type",
    "rank_type",
    "rank_scope",
    "award_scope",
    "award_places",
    "place",
    "field_size",
    "athlete_name",
    "team_name",
    "class",
    "gender_context",
    "score_seconds",
    "margin_to_leader",
    "margin_to_previous_place",
    "inside_award_places",
)

SQUAD_RESULT_COLUMNS = (
    "match_id",
    "match_name",
    "discipline_id",
    "discipline",
    "leaderboard_name",
    "rank_scope",
    "award_scope",
    "squad_place",
    "squad_name",
    "squad_score_seconds",
    "athlete_count",
    "athlete_1_name",
    "athlete_1_score",
    "athlete_2_name",
    "athlete_2_score",
    "athlete_3_name",
    "athlete_3_score",
    "athlete_4_name",
    "athlete_4_score",
    "margin_to_leader",
    "margin_to_previous_place",
    "inside_award_places",
)

STAGE_SCORE_COLUMNS = (
    "match_id",
    "match_name",
    "athlete_id",
    "athlete_name",
    "team_name",
    "class",
    "gender",
    "discipline_id",
    "discipline",
    "stage_number",
    "stage_name",
    "stage_score_seconds",
    "fastest_string_seconds",
    "scored_avg_string_seconds",
    "dropped_string_count",
    "penalty_count",
)


class MatchParseError(RuntimeError):
    """Raised when raw match snapshots cannot be parsed."""


@dataclass(frozen=True)
class ParseResult:
    match_scores_path: Path
    rankings_path: Path
    squad_results_path: Path
    stage_scores_path: Path
    match_score_rows: int
    ranking_rows: int
    squad_result_rows: int
    stage_score_rows: int
    warnings: tuple[str, ...]


def parse_match(
    match_id: int,
    output_dir: Path | str,
) -> ParseResult:
    """Parse one match's slots and leaderboard snapshots into CSV tables."""
    output_path = Path(output_dir)
    raw_dir = output_path / "raw"
    tables_dir = output_path / "tables"
    slots_path = raw_dir / f"{match_id}_slots.json"
    leaderboard_path = raw_dir / f"{match_id}_leaderboard.json"

    slots = _load_json(slots_path)
    leaderboard = _load_json(leaderboard_path)
    if not isinstance(slots, list):
        raise MatchParseError(f"Slots snapshot must be a list: {slots_path}")
    if not isinstance(leaderboard, dict):
        raise MatchParseError(
            f"Leaderboard snapshot must be an object: {leaderboard_path}"
        )

    leaderboard_match_id = leaderboard.get("id")
    if leaderboard_match_id not in (None, match_id):
        raise MatchParseError(
            f"Leaderboard match ID {leaderboard_match_id!r} does not "
            f"match requested match ID {match_id}."
        )

    match_name = _text(leaderboard.get("name"))
    stage_names = {
        1: _text(leaderboard.get("stage_one")),
        2: _text(leaderboard.get("stage_two")),
        3: _text(leaderboard.get("stage_three")),
        4: _text(leaderboard.get("stage_four")),
    }

    warning_counts: Counter[str] = Counter()
    match_score_rows, stage_score_rows = _parse_slots(
        slots,
        match_id,
        match_name,
        stage_names,
        warning_counts,
    )
    ranking_rows, squad_result_rows = _parse_leaderboards(
        leaderboard,
        match_id,
        match_name,
        warning_counts,
    )

    _ensure_directory(tables_dir)
    match_scores_path = tables_dir / "match_scores.csv"
    rankings_path = tables_dir / "rankings.csv"
    squad_results_path = tables_dir / "squad_results.csv"
    stage_scores_path = tables_dir / "stage_scores.csv"

    _write_csv(match_scores_path, MATCH_SCORE_COLUMNS, match_score_rows)
    _write_csv(rankings_path, RANKING_COLUMNS, ranking_rows)
    _write_csv(
        squad_results_path,
        SQUAD_RESULT_COLUMNS,
        squad_result_rows,
    )
    _write_csv(stage_scores_path, STAGE_SCORE_COLUMNS, stage_score_rows)

    return ParseResult(
        match_scores_path=match_scores_path,
        rankings_path=rankings_path,
        squad_results_path=squad_results_path,
        stage_scores_path=stage_scores_path,
        match_score_rows=len(match_score_rows),
        ranking_rows=len(ranking_rows),
        squad_result_rows=len(squad_result_rows),
        stage_score_rows=len(stage_score_rows),
        warnings=_format_warnings(warning_counts),
    )


def _parse_slots(
    slots: list[Any],
    match_id: int,
    match_name: str,
    stage_names: dict[int, str],
    warning_counts: Counter[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    match_rows: list[dict[str, Any]] = []
    stage_rows: list[dict[str, Any]] = []
    athlete_discipline_counts: Counter[tuple[Any, Any]] = Counter()

    for slot in slots:
        if not isinstance(slot, dict):
            warning_counts["non_object_slot"] += 1
            continue
        slot_match_id = slot.get("comp_id")
        if slot_match_id not in (None, match_id):
            warning_counts["slot_match_id_mismatch"] += 1

        discipline = _mapping(slot.get("discipline"))
        discipline_id = slot.get("disc_id") or discipline.get("id")
        discipline_name = _text(discipline.get("descr"))
        hosting_team = _mapping(slot.get("hosting_team"))

        lineup = slot.get("lineup")
        if not isinstance(lineup, list):
            warning_counts["missing_lineup_list"] += 1
            continue

        for athlete in lineup:
            if not isinstance(athlete, dict):
                warning_counts["non_object_lineup_row"] += 1
                continue

            athlete_id = athlete.get("ath_id")
            athlete_name = _text(athlete.get("name"))
            team_name = (
                _text(athlete.get("team"))
                or _text(hosting_team.get("name"))
            )
            athlete_discipline_counts[(athlete_id, discipline_id)] += 1
            match_score = _number_or_blank(athlete.get("spp_final"))
            if match_score == "":
                warning_counts["missing_match_score"] += 1
            if not athlete_name:
                warning_counts["missing_athlete_name"] += 1
            if _number(athlete.get("proc_pen")) not in (None, 0):
                warning_counts[
                    "procedural_penalty_not_in_stage_scores"
                ] += 1

            common = {
                "match_id": match_id,
                "match_name": match_name,
                "athlete_id": athlete_id,
                "athlete_name": athlete_name,
                "team_name": team_name,
                "class": _text(athlete.get("class")),
                "gender": _text(athlete.get("gender")),
                "discipline_id": discipline_id,
                "discipline": discipline_name,
            }
            match_rows.append(
                {
                    **common,
                    "match_score_seconds": match_score,
                    "dnf_flag": bool(athlete.get("dnf_tag")),
                    "dq_flag": bool(athlete.get("dq_tag")),
                }
            )

            for stage_number in range(1, 5):
                stage_rows.append(
                    {
                        **common,
                        **_stage_values(
                            athlete,
                            stage_number,
                            stage_names.get(stage_number, ""),
                            warning_counts,
                        ),
                    }
                )

    duplicate_count = sum(
        count - 1
        for count in athlete_discipline_counts.values()
        if count > 1
    )
    warning_counts["duplicate_athlete_discipline_entries"] += duplicate_count
    return match_rows, stage_rows


def _stage_values(
    athlete: dict[str, Any],
    stage_number: int,
    stage_name: str,
    warning_counts: Counter[str],
) -> dict[str, Any]:
    totals = [
        _number(athlete.get(f"spp{stage_number}_tot{string_number}"))
        for string_number in range(1, 6)
    ]
    nonzero_totals = [
        value for value in totals if value is not None and value != 0
    ]
    penalties = [
        _number(athlete.get(f"spp{stage_number}_pen{string_number}"))
        for string_number in range(1, 6)
    ]
    penalty_count = sum(value or 0 for value in penalties)
    dropped_string_count = 5 - len(nonzero_totals)

    if not nonzero_totals:
        warning_counts["unscored_stage"] += 1
        stage_score: float | str = ""
        fastest_string: float | str = ""
        scored_average: float | str = ""
    else:
        if len(nonzero_totals) != 4:
            warning_counts[
                f"stage_with_{len(nonzero_totals)}_counting_strings"
            ] += 1
        counting_strings = sorted(nonzero_totals)[:4]
        if len(counting_strings) < 4:
            stage_score = ""
            scored_average = ""
        else:
            stage_score = round(sum(counting_strings), 2)
            scored_average = round(stage_score / 4, 4)
        fastest_string = min(nonzero_totals)

    return {
        "stage_number": stage_number,
        "stage_name": stage_name,
        "stage_score_seconds": stage_score,
        "fastest_string_seconds": fastest_string,
        "scored_avg_string_seconds": scored_average,
        "dropped_string_count": dropped_string_count,
        "penalty_count": _clean_number(penalty_count),
    }


def _parse_leaderboards(
    leaderboard: dict[str, Any],
    match_id: int,
    match_name: str,
    warning_counts: Counter[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ranking_rows: list[dict[str, Any]] = []
    squad_rows: list[dict[str, Any]] = []
    disciplines = leaderboard.get("disciplines")
    if not isinstance(disciplines, list):
        raise MatchParseError("Leaderboard is missing a disciplines list.")

    for discipline in disciplines:
        if not isinstance(discipline, dict):
            warning_counts["non_object_discipline"] += 1
            continue
        discipline_id = discipline.get("id")
        discipline_name = _text(discipline.get("descr"))
        boards = discipline.get("leaderboards")
        if not isinstance(boards, list):
            warning_counts["missing_leaderboards_list"] += 1
            continue

        for board in boards:
            if not isinstance(board, dict):
                warning_counts["non_object_leaderboard"] += 1
                continue
            board_type = _text(board.get("type")).lower()
            if board_type == "athlete":
                ranking_rows.extend(
                    _parse_athlete_board(
                        board,
                        match_id,
                        match_name,
                        discipline_id,
                        discipline_name,
                        warning_counts,
                    )
                )
            elif board_type == "squad":
                squad_rows.extend(
                    _parse_squad_board(
                        board,
                        match_id,
                        match_name,
                        discipline_id,
                        discipline_name,
                        warning_counts,
                    )
                )
            else:
                warning_counts["unknown_leaderboard_type"] += 1

    return ranking_rows, squad_rows


def _parse_athlete_board(
    board: dict[str, Any],
    match_id: int,
    match_name: str,
    discipline_id: Any,
    discipline_name: str,
    warning_counts: Counter[str],
) -> list[dict[str, Any]]:
    data = board.get("data")
    if not isinstance(data, list):
        warning_counts["missing_athlete_board_data"] += 1
        return []

    leaderboard_name = _text(board.get("name"))
    rank_scope = _text(board.get("class"))
    award_places = _integer_or_blank(board.get("places"))
    rank_type, award_scope, gender_context = _athlete_rank_context(
        leaderboard_name,
        rank_scope,
    )
    scores = [_number(row.get("time")) for row in data if isinstance(row, dict)]
    leader_score = next((score for score in scores if score is not None), None)
    previous_score: float | None = None
    rows: list[dict[str, Any]] = []

    for row in data:
        if not isinstance(row, dict):
            warning_counts["non_object_ranking_row"] += 1
            continue
        score = _number(row.get("time"))
        place = _integer_or_blank(row.get("place"))
        rows.append(
            {
                "match_id": match_id,
                "match_name": match_name,
                "discipline_id": discipline_id,
                "discipline": discipline_name,
                "leaderboard_name": leaderboard_name,
                "leaderboard_type": "athlete",
                "rank_type": rank_type,
                "rank_scope": rank_scope,
                "award_scope": award_scope,
                "award_places": award_places,
                "place": place,
                "field_size": len(data),
                "athlete_name": _text(row.get("athlete")),
                "team_name": _text(row.get("team")),
                "class": _text(row.get("class")),
                "gender_context": gender_context,
                "score_seconds": _clean_number(score),
                "margin_to_leader": _margin(score, leader_score),
                "margin_to_previous_place": _margin(
                    score,
                    previous_score,
                ),
                "inside_award_places": _inside_awards(
                    place,
                    award_places,
                    award_scope,
                ),
            }
        )
        if score is not None:
            previous_score = score

    return rows


def _parse_squad_board(
    board: dict[str, Any],
    match_id: int,
    match_name: str,
    discipline_id: Any,
    discipline_name: str,
    warning_counts: Counter[str],
) -> list[dict[str, Any]]:
    teams = board.get("teams")
    if not isinstance(teams, list):
        warning_counts["missing_squad_board_data"] += 1
        return []

    leaderboard_name = _text(board.get("name"))
    rank_scope = _text(board.get("class"))
    award_places = _integer_or_blank(board.get("places"))
    scores = [
        _number(team.get("score"))
        for team in teams
        if isinstance(team, dict)
    ]
    leader_score = next((score for score in scores if score is not None), None)
    previous_score: float | None = None
    rows: list[dict[str, Any]] = []

    for squad_place, team in enumerate(teams, start=1):
        if not isinstance(team, dict):
            warning_counts["non_object_squad_row"] += 1
            continue
        athletes = team.get("athletes")
        if not isinstance(athletes, list):
            athletes = []
            warning_counts["missing_squad_athletes"] += 1
        if len(athletes) > 4:
            warning_counts["squad_with_more_than_four_athletes"] += 1

        score = _number(team.get("score"))
        row = {
            "match_id": match_id,
            "match_name": match_name,
            "discipline_id": discipline_id,
            "discipline": discipline_name,
            "leaderboard_name": leaderboard_name,
            "rank_scope": rank_scope,
            "award_scope": "Division",
            "squad_place": squad_place,
            "squad_name": _text(team.get("squad_name")),
            "squad_score_seconds": _clean_number(score),
            "athlete_count": len(athletes),
            "margin_to_leader": _margin(score, leader_score),
            "margin_to_previous_place": _margin(
                score,
                previous_score,
            ),
            "inside_award_places": _inside_awards(
                squad_place,
                award_places,
                "Division",
            ),
        }
        for athlete_number in range(1, 5):
            athlete = (
                athletes[athlete_number - 1]
                if athlete_number <= len(athletes)
                and isinstance(athletes[athlete_number - 1], dict)
                else {}
            )
            row[f"athlete_{athlete_number}_name"] = _text(
                athlete.get("name")
            )
            row[f"athlete_{athlete_number}_score"] = _number_or_blank(
                athlete.get("spp_final")
            )
        rows.append(row)
        if score is not None:
            previous_score = score

    return rows


def _athlete_rank_context(
    leaderboard_name: str,
    rank_scope: str,
) -> tuple[str, str, str]:
    normalized_name = leaderboard_name.casefold()
    if "ladies" in normalized_name:
        gender_context = "F"
    elif "men" in normalized_name:
        gender_context = "M"
    else:
        gender_context = ""

    if "athlete" in normalized_name and rank_scope.casefold() == "all":
        return ("overall_discipline", "Comparison", gender_context)
    if rank_scope.casefold() == "all":
        return ("individual_hoa", "Class", gender_context)
    return ("individual_class", "Class", gender_context)


def _inside_awards(
    place: int | str,
    award_places: int | str,
    award_scope: str,
) -> bool | str:
    if award_scope == "Comparison":
        return ""
    if not isinstance(place, int) or not isinstance(award_places, int):
        return ""
    return place <= award_places


def _margin(
    score: float | None,
    comparison: float | None,
) -> float | str:
    if score is None or comparison is None:
        return ""
    return round(score - comparison, 2)


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as source:
            return json.load(source)
    except FileNotFoundError as exc:
        raise MatchParseError(f"Missing raw snapshot: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise MatchParseError(f"Could not read raw snapshot {path}: {exc}") from exc


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
        raise MatchParseError(f"Could not write table {path}: {exc}") from exc


def _ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MatchParseError(
            f"Could not create tables directory {path}: {exc}"
        ) from exc
    if not path.is_dir():
        raise MatchParseError(f"Tables path is not a directory: {path}")


def _format_warnings(warning_counts: Counter[str]) -> tuple[str, ...]:
    labels = {
        "duplicate_athlete_discipline_entries": (
            "duplicate athlete/discipline entries preserved"
        ),
        "missing_athlete_name": "slot entries missing athlete name",
        "missing_match_score": "slot entries missing match score",
        "procedural_penalty_not_in_stage_scores": (
            "entries had match-level procedural penalties not included "
            "in stage score fields"
        ),
        "stage_with_5_counting_strings": (
            "stages had five non-zero totals; four fastest were used"
        ),
        "unscored_stage": "stages had no non-zero scored totals",
    }
    return tuple(
        f"{count} {labels.get(key, key.replace('_', ' '))}"
        for key, count in sorted(warning_counts.items())
        if count
    )


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _number(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_number(value: float | None) -> float | int | str:
    if value is None:
        return ""
    if value.is_integer():
        return int(value)
    return value


def _number_or_blank(value: Any) -> float | int | str:
    return _clean_number(_number(value))


def _integer_or_blank(value: Any) -> int | str:
    if value in (None, "") or isinstance(value, bool):
        return ""
    try:
        return int(value)
    except (TypeError, ValueError):
        return ""
