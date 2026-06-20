"""Nationals refresh snapshots, comparisons, and coach brief outputs."""

from __future__ import annotations

import csv
import hashlib
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from wilco_as_reporting.team_profiles import TeamProfile

CHANGE_SUMMARY_COLUMNS = (
    "match_id",
    "team_key",
    "current_snapshot",
    "previous_snapshot",
    "comparison_status",
    "data_status",
    "athlete_count_current",
    "athlete_count_previous",
    "changed_athlete_count",
    "changed_award_count",
    "changed_squad_count",
    "new_review_count",
    "resolved_review_count",
    "validation_error_count",
    "validation_warning_count",
    "validation_review_count",
    "notes",
)

ATHLETE_CHANGE_COLUMNS = (
    "match_id",
    "team_key",
    "athlete_id",
    "athlete_name",
    "discipline",
    "previous_score_seconds",
    "current_score_seconds",
    "score_change_seconds",
    "previous_best_place",
    "current_best_place",
    "place_change",
    "change_type",
    "notes",
)

AWARD_CHANGE_COLUMNS = (
    "match_id",
    "team_key",
    "discipline",
    "leaderboard_name",
    "rank_scope",
    "award_scope",
    "athlete_name",
    "previous_place",
    "current_place",
    "place_change",
    "previous_inside_award_places",
    "current_inside_award_places",
    "change_type",
    "notes",
)

SQUAD_CHANGE_COLUMNS = (
    "match_id",
    "team_key",
    "discipline",
    "squad_name",
    "previous_squad_place",
    "current_squad_place",
    "place_change",
    "previous_squad_score_seconds",
    "current_squad_score_seconds",
    "score_change_seconds",
    "change_type",
    "notes",
)

STAGE_CHANGE_COLUMNS = (
    "match_id",
    "team_key",
    "athlete_id",
    "athlete_name",
    "discipline",
    "stage_number",
    "stage_name",
    "previous_stage_score_seconds",
    "current_stage_score_seconds",
    "stage_score_change_seconds",
    "change_type",
    "notes",
)

REVIEW_CHANGE_COLUMNS = (
    "match_id",
    "team_key",
    "severity",
    "check_name",
    "finding_type",
    "athlete_name",
    "discipline",
    "stage_name",
    "previous_status",
    "current_status",
    "change_type",
    "message",
    "notes",
)

DAILY_BRIEF_COLUMNS = (
    "match_id",
    "team_key",
    "brief_section",
    "priority",
    "title",
    "detail",
    "related_athlete",
    "related_discipline",
    "related_squad",
    "notes",
)

MANIFEST_COLUMNS = (
    "match_id",
    "team_key",
    "match_name",
    "run_timestamp",
    "snapshot_label",
    "snapshot_path",
    "raw_slots_hash",
    "raw_leaderboard_hash",
    "raw_schedule_hash",
    "team_report_hash",
    "workbook_hash",
    "athlete_count",
    "entry_count",
    "stage_row_count",
    "validation_error_count",
    "validation_warning_count",
    "validation_review_count",
    "data_status",
    "notes",
)

OPS_FILES = (
    ("wilco_change_summary.csv", CHANGE_SUMMARY_COLUMNS),
    ("wilco_athlete_changes.csv", ATHLETE_CHANGE_COLUMNS),
    ("wilco_award_changes.csv", AWARD_CHANGE_COLUMNS),
    ("wilco_squad_changes.csv", SQUAD_CHANGE_COLUMNS),
    ("wilco_stage_changes.csv", STAGE_CHANGE_COLUMNS),
    ("wilco_review_changes.csv", REVIEW_CHANGE_COLUMNS),
    ("wilco_daily_brief.csv", DAILY_BRIEF_COLUMNS),
)

SNAPSHOT_ITEMS = (
    "raw",
    "tables",
    "validation",
    "report_tables",
    "workbooks",
    "team_report_tables",
    "nationals_ops",
)


class NationalsOpsError(RuntimeError):
    """Raised when Nationals operations outputs cannot be generated."""


@dataclass(frozen=True)
class NationalsOpsResult:
    snapshot_path: Path
    previous_snapshot_path: Path | None
    manifest_path: Path
    operations_dir: Path
    workbook_path: Path
    comparison_status: str
    data_status: str
    changed_athlete_count: int
    changed_award_count: int
    changed_squad_count: int
    new_review_count: int
    resolved_review_count: int
    validation_counts: dict[str, int]
    row_counts: dict[str, int]
    notes: tuple[str, ...]


def build_nationals_operations(
    match_id: int,
    output_dir: Path | str,
    profile: TeamProfile,
    snapshot_label: str = "manual",
) -> NationalsOpsResult:
    """Compare the current team build, preserve it, and update state."""
    output_path = Path(output_dir)
    label = _safe_label(snapshot_label)
    run_time = datetime.now().astimezone()
    run_timestamp = run_time.strftime("%Y%m%d_%H%M%S")
    snapshot_path = _unique_snapshot_path(
        output_path / "snapshots",
        run_timestamp,
        profile.team_key,
        label,
    )
    previous_snapshot = _find_previous_snapshot(
        output_path / "snapshots",
        profile.team_key,
    )
    operations_dir = (
        output_path / "nationals_ops" / profile.team_key
    )
    team_dir = (
        output_path / "team_report_tables" / profile.team_key
    )

    current = _load_sources(output_path, team_dir, profile)
    previous = (
        _load_sources(
            previous_snapshot,
            previous_snapshot
            / "team_report_tables"
            / profile.team_key,
            profile,
            allow_missing=True,
        )
        if previous_snapshot
        else None
    )
    comparison_status = (
        "COMPARED"
        if previous is not None and previous["compatible"]
        else "BASELINE"
        if previous_snapshot is None
        else "UNAVAILABLE"
    )
    data_status, status_notes = _data_status(current)

    athlete_changes = _athlete_changes(
        match_id,
        profile,
        current,
        previous if comparison_status == "COMPARED" else None,
    )
    award_changes = _award_changes(
        match_id,
        profile,
        current["awards"],
        (
            previous["awards"]
            if comparison_status == "COMPARED"
            else None
        ),
    )
    squad_changes = _squad_changes(
        match_id,
        profile,
        current["squads"],
        (
            previous["squads"]
            if comparison_status == "COMPARED"
            else None
        ),
    )
    stage_changes = _stage_changes(
        match_id,
        profile,
        current["stages"],
        (
            previous["stages"]
            if comparison_status == "COMPARED"
            else None
        ),
    )
    review_changes = _review_changes(
        match_id,
        profile,
        current["reviews"],
        (
            previous["reviews"]
            if comparison_status == "COMPARED"
            else None
        ),
    )

    changed_athlete_count = len(
        {
            (
                row["athlete_id"],
                row["athlete_name"],
            )
            for row in athlete_changes
            if row["change_type"]
            not in {"unchanged", "baseline", "incomplete"}
        }
    )
    changed_award_count = _changed_count(award_changes)
    changed_squad_count = _changed_count(squad_changes)
    new_review_count = sum(
        row["change_type"] == "new_review"
        for row in review_changes
    )
    resolved_review_count = sum(
        row["change_type"] == "resolved"
        for row in review_changes
    )
    previous_athlete_count = (
        _summary_integer(previous, "athlete_count")
        if previous
        else 0
    )
    validation_counts = {
        severity: _summary_integer(
            current,
            f"validation_{severity.casefold()}_count",
        )
        for severity in ("ERROR", "WARNING", "REVIEW")
    }
    comparison_notes = list(status_notes)
    if comparison_status == "BASELINE":
        comparison_notes.append(
            "No prior snapshot was available; this run is the baseline."
        )
    elif comparison_status == "UNAVAILABLE":
        comparison_notes.append(
            "A prior snapshot exists, but compatible comparison files "
            "were unavailable."
        )

    summary_rows = [
        {
            "match_id": match_id,
            "team_key": profile.team_key,
            "current_snapshot": str(snapshot_path),
            "previous_snapshot": (
                str(previous_snapshot) if previous_snapshot else ""
            ),
            "comparison_status": comparison_status,
            "data_status": data_status,
            "athlete_count_current": _summary_integer(
                current,
                "athlete_count",
            ),
            "athlete_count_previous": previous_athlete_count,
            "changed_athlete_count": changed_athlete_count,
            "changed_award_count": changed_award_count,
            "changed_squad_count": changed_squad_count,
            "new_review_count": new_review_count,
            "resolved_review_count": resolved_review_count,
            "validation_error_count": validation_counts["ERROR"],
            "validation_warning_count": validation_counts["WARNING"],
            "validation_review_count": validation_counts["REVIEW"],
            "notes": " ".join(comparison_notes),
        }
    ]
    brief_rows = _daily_brief(
        match_id,
        profile,
        comparison_status,
        data_status,
        status_notes,
        athlete_changes,
        award_changes,
        squad_changes,
        review_changes,
        validation_counts,
    )
    output_rows = {
        "wilco_change_summary.csv": summary_rows,
        "wilco_athlete_changes.csv": athlete_changes,
        "wilco_award_changes.csv": award_changes,
        "wilco_squad_changes.csv": squad_changes,
        "wilco_stage_changes.csv": stage_changes,
        "wilco_review_changes.csv": review_changes,
        "wilco_daily_brief.csv": brief_rows,
    }
    operations_dir.mkdir(parents=True, exist_ok=True)
    for filename, columns in OPS_FILES:
        _write_csv(
            operations_dir / filename,
            columns,
            output_rows[filename],
        )

    from wilco_as_reporting.workbooks.nationals_excel_writer import (
        build_nationals_workbook,
    )

    workbook_result = build_nationals_workbook(
        match_id=match_id,
        output_dir=output_path,
        profile=profile,
        generated_at=run_time.isoformat(timespec="seconds"),
        snapshot_label=label,
        current_snapshot=snapshot_path,
        previous_snapshot=previous_snapshot,
        comparison_status=comparison_status,
        data_status=data_status,
        validation_counts=validation_counts,
        notes=tuple(status_notes),
    )
    _preserve_snapshot(output_path, snapshot_path)

    manifest_path = (
        output_path.parent / "state" / "match_refresh_manifest.csv"
    )
    manifest_notes = list(status_notes)
    hashes = _artifact_hashes(output_path, profile)
    missing_hashes = [
        name
        for name, value in hashes.items()
        if not value
    ]
    if missing_hashes:
        manifest_notes.append(
            "Missing optional artifact hash(es): "
            + ", ".join(missing_hashes)
            + "."
        )
    _append_manifest(
        manifest_path,
        {
            "match_id": match_id,
            "team_key": profile.team_key,
            "match_name": current["match_name"],
            "run_timestamp": run_time.isoformat(timespec="seconds"),
            "snapshot_label": label,
            "snapshot_path": str(snapshot_path),
            **hashes,
            "athlete_count": _summary_integer(
                current,
                "athlete_count",
            ),
            "entry_count": _summary_integer(
                current,
                "entry_count",
            ),
            "stage_row_count": len(current["stages"]),
            "validation_error_count": validation_counts["ERROR"],
            "validation_warning_count": validation_counts["WARNING"],
            "validation_review_count": validation_counts["REVIEW"],
            "data_status": data_status,
            "notes": " ".join(manifest_notes),
        },
    )

    return NationalsOpsResult(
        snapshot_path=snapshot_path,
        previous_snapshot_path=previous_snapshot,
        manifest_path=manifest_path,
        operations_dir=operations_dir,
        workbook_path=workbook_result.path,
        comparison_status=comparison_status,
        data_status=data_status,
        changed_athlete_count=changed_athlete_count,
        changed_award_count=changed_award_count,
        changed_squad_count=changed_squad_count,
        new_review_count=new_review_count,
        resolved_review_count=resolved_review_count,
        validation_counts=validation_counts,
        row_counts={
            filename: len(output_rows[filename])
            for filename, _ in OPS_FILES
        },
        notes=tuple(comparison_notes),
    )


def _load_sources(
    root: Path,
    team_dir: Path,
    profile: TeamProfile,
    *,
    allow_missing: bool = False,
) -> dict[str, Any]:
    paths = {
        "summary": team_dir / "wilco_team_summary.csv",
        "awards": team_dir / "wilco_award_highlights.csv",
        "comparisons": team_dir / "wilco_comparison_results.csv",
        "squads": team_dir / "wilco_squad_summary.csv",
        "stages": team_dir / "wilco_stage_coach_view.csv",
        "reviews": team_dir / "wilco_coach_review_queue.csv",
        "scores": root / "tables" / "match_scores.csv",
    }
    missing = [
        path
        for path in paths.values()
        if not path.exists()
    ]
    if missing and not allow_missing:
        raise NationalsOpsError(
            "Missing Nationals operations input(s): "
            + ", ".join(str(path) for path in missing)
        )
    rows = {
        name: _read_csv(path) if path.exists() else []
        for name, path in paths.items()
    }
    rows["scores"] = [
        row
        for row in rows["scores"]
        if profile.matches_name(row.get("team_name"))
    ]
    summary = rows["summary"][0] if rows["summary"] else {}
    rows["summary_row"] = summary
    rows["match_name"] = (
        summary.get("match_name")
        or next(
            (
                row.get("match_name", "")
                for row in rows["scores"]
                if row.get("match_name")
            ),
            "",
        )
    )
    rows["compatible"] = not missing and bool(rows["summary"])
    return rows


def _data_status(current: dict[str, Any]) -> tuple[str, list[str]]:
    scores = current["scores"]
    scored = sum(bool(row.get("match_score_seconds")) for row in scores)
    missing_scores = len(scores) - scored
    no_rankings = not current["awards"] and not current["comparisons"]
    notes: list[str] = []
    if not scores or scored == 0:
        status = "no_scores"
        notes.append("No final Wilco scores are currently available.")
    elif missing_scores or no_rankings:
        status = "partial"
    else:
        status = "complete"
    if missing_scores:
        notes.append(
            f"{missing_scores} Wilco discipline entries lack final scores."
        )
    if no_rankings:
        notes.append(
            "No Wilco individual award or comparison rankings are "
            "currently available."
        )
    if status == "complete" and _summary_integer(
        current,
        "validation_error_count",
    ):
        status = "validation_errors_present"
        notes.append(
            "Final data is present, but validation errors require review."
        )
    return status, notes


def _athlete_changes(
    match_id: int,
    profile: TeamProfile,
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    current_rows = _score_index(current)
    previous_rows = _score_index(previous) if previous else {}
    keys = sorted(
        set(current_rows) | set(previous_rows),
        key=lambda key: (key[1].casefold(), key[2].casefold(), key[0]),
    )
    rows: list[dict[str, Any]] = []
    for key in keys:
        current_row = current_rows.get(key)
        previous_row = previous_rows.get(key)
        current_score = _number(
            current_row.get("match_score_seconds")
            if current_row
            else None
        )
        previous_score = _number(
            previous_row.get("match_score_seconds")
            if previous_row
            else None
        )
        current_place = _best_place(current, key[1], key[2])
        previous_place = (
            _best_place(previous, key[1], key[2])
            if previous
            else None
        )
        change_type, notes = _athlete_change_type(
            current_row,
            previous_row,
            current_score,
            previous_score,
            current_place,
            previous_place,
            previous is None,
        )
        rows.append(
            {
                "match_id": match_id,
                "team_key": profile.team_key,
                "athlete_id": key[0],
                "athlete_name": key[1],
                "discipline": key[2],
                "previous_score_seconds": _display(previous_score),
                "current_score_seconds": _display(current_score),
                "score_change_seconds": _difference(
                    current_score,
                    previous_score,
                ),
                "previous_best_place": _display(previous_place),
                "current_best_place": _display(current_place),
                "place_change": _difference(
                    current_place,
                    previous_place,
                ),
                "change_type": change_type,
                "notes": notes,
            }
        )
    return rows


def _score_index(
    source: dict[str, Any] | None,
) -> dict[tuple[str, str, str], dict[str, str]]:
    if not source:
        return {}
    indexed: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in source["scores"]:
        key = (
            row.get("athlete_id", ""),
            row.get("athlete_name", ""),
            row.get("discipline", ""),
        )
        existing = indexed.get(key)
        if not existing or (
            not existing.get("match_score_seconds")
            and row.get("match_score_seconds")
        ):
            indexed[key] = row
    return indexed


def _best_place(
    source: dict[str, Any] | None,
    athlete_name: str,
    discipline: str,
) -> int | None:
    if not source:
        return None
    places = [
        value
        for value in (
            _integer(row.get("place"))
            for row in [
                *source["awards"],
                *source["comparisons"],
            ]
            if row.get("athlete_name") == athlete_name
            and row.get("discipline") == discipline
        )
        if value is not None
    ]
    return min(places) if places else None


def _athlete_change_type(
    current_row: dict[str, str] | None,
    previous_row: dict[str, str] | None,
    current_score: float | None,
    previous_score: float | None,
    current_place: int | None,
    previous_place: int | None,
    baseline: bool,
) -> tuple[str, str]:
    if baseline:
        return "baseline", "First snapshot for this match and team."
    if current_row is None:
        return "removed_or_missing", "Entry is absent from current data."
    if previous_row is None:
        if current_score is None:
            return "incomplete", "New entry has no final score yet."
        return "new_score", "New scored entry since the prior snapshot."
    if current_score is None:
        return "incomplete", "Current entry has no final score."
    if previous_score is None:
        return "new_score", "A final score is now available."
    if not _same_number(current_score, previous_score):
        return "score_changed", "Final score changed."
    if current_place != previous_place:
        return "place_changed", "Best available place changed."
    return "unchanged", ""


def _award_changes(
    match_id: int,
    profile: TeamProfile,
    current: list[dict[str, str]],
    previous: list[dict[str, str]] | None,
) -> list[dict[str, Any]]:
    key_fields = (
        "discipline",
        "leaderboard_name",
        "rank_scope",
        "award_scope",
        "athlete_name",
    )
    current_index = _index_rows(current, key_fields)
    previous_index = _index_rows(previous or [], key_fields)
    rows: list[dict[str, Any]] = []
    for key in sorted(
        set(current_index) | set(previous_index),
        key=lambda item: tuple(value.casefold() for value in item),
    ):
        current_row = current_index.get(key)
        previous_row = previous_index.get(key)
        current_place = _integer(
            current_row.get("place") if current_row else None
        )
        previous_place = _integer(
            previous_row.get("place") if previous_row else None
        )
        change_type = _placement_change_type(
            current_row,
            previous_row,
            current_place,
            previous_place,
            previous is None,
        )
        rows.append(
            {
                "match_id": match_id,
                "team_key": profile.team_key,
                **dict(zip(key_fields, key)),
                "previous_place": _display(previous_place),
                "current_place": _display(current_place),
                "place_change": _difference(
                    current_place,
                    previous_place,
                ),
                "previous_inside_award_places": (
                    previous_row.get("inside_award_places", "")
                    if previous_row
                    else ""
                ),
                "current_inside_award_places": (
                    current_row.get("inside_award_places", "")
                    if current_row
                    else ""
                ),
                "change_type": change_type,
                "notes": _placement_note(change_type),
            }
        )
    return rows


def _squad_changes(
    match_id: int,
    profile: TeamProfile,
    current: list[dict[str, str]],
    previous: list[dict[str, str]] | None,
) -> list[dict[str, Any]]:
    key_fields = ("discipline", "squad_name")
    current_index = _index_rows(current, key_fields)
    previous_index = _index_rows(previous or [], key_fields)
    rows: list[dict[str, Any]] = []
    for key in sorted(
        set(current_index) | set(previous_index),
        key=lambda item: tuple(value.casefold() for value in item),
    ):
        current_row = current_index.get(key)
        previous_row = previous_index.get(key)
        current_place = _integer(
            current_row.get("squad_place") if current_row else None
        )
        previous_place = _integer(
            previous_row.get("squad_place") if previous_row else None
        )
        current_score = _number(
            current_row.get("squad_score_seconds")
            if current_row
            else None
        )
        previous_score = _number(
            previous_row.get("squad_score_seconds")
            if previous_row
            else None
        )
        change_type = _score_place_change_type(
            current_row,
            previous_row,
            current_score,
            previous_score,
            current_place,
            previous_place,
            previous is None,
        )
        rows.append(
            {
                "match_id": match_id,
                "team_key": profile.team_key,
                "discipline": key[0],
                "squad_name": key[1],
                "previous_squad_place": _display(previous_place),
                "current_squad_place": _display(current_place),
                "place_change": _difference(
                    current_place,
                    previous_place,
                ),
                "previous_squad_score_seconds": _display(
                    previous_score
                ),
                "current_squad_score_seconds": _display(current_score),
                "score_change_seconds": _difference(
                    current_score,
                    previous_score,
                ),
                "change_type": change_type,
                "notes": _placement_note(change_type),
            }
        )
    return rows


def _stage_changes(
    match_id: int,
    profile: TeamProfile,
    current: list[dict[str, str]],
    previous: list[dict[str, str]] | None,
) -> list[dict[str, Any]]:
    key_fields = (
        "athlete_id",
        "athlete_name",
        "discipline",
        "stage_number",
        "stage_name",
    )
    current_index = _index_rows(current, key_fields)
    previous_index = _index_rows(previous or [], key_fields)
    rows: list[dict[str, Any]] = []
    for key in sorted(
        set(current_index) | set(previous_index),
        key=lambda item: (
            item[1].casefold(),
            item[2].casefold(),
            _integer(item[3]) or 0,
        ),
    ):
        current_row = current_index.get(key)
        previous_row = previous_index.get(key)
        current_score = _number(
            current_row.get("stage_score_seconds")
            if current_row
            else None
        )
        previous_score = _number(
            previous_row.get("stage_score_seconds")
            if previous_row
            else None
        )
        change_type = _simple_score_change_type(
            current_row,
            previous_row,
            current_score,
            previous_score,
            previous is None,
        )
        rows.append(
            {
                "match_id": match_id,
                "team_key": profile.team_key,
                **dict(zip(key_fields, key)),
                "previous_stage_score_seconds": _display(
                    previous_score
                ),
                "current_stage_score_seconds": _display(current_score),
                "stage_score_change_seconds": _difference(
                    current_score,
                    previous_score,
                ),
                "change_type": change_type,
                "notes": _placement_note(change_type),
            }
        )
    return rows


def _review_changes(
    match_id: int,
    profile: TeamProfile,
    current: list[dict[str, str]],
    previous: list[dict[str, str]] | None,
) -> list[dict[str, Any]]:
    key_fields = (
        "severity",
        "check_name",
        "finding_type",
        "athlete_name",
        "discipline",
        "stage_name",
        "message",
    )
    current_index = _index_rows(current, key_fields)
    previous_index = _index_rows(previous or [], key_fields)
    rows: list[dict[str, Any]] = []
    for key in sorted(
        set(current_index) | set(previous_index),
        key=lambda item: (
            item[0],
            item[3].casefold(),
            item[4].casefold(),
            item[5].casefold(),
        ),
    ):
        in_current = key in current_index
        in_previous = key in previous_index
        if previous is None:
            change_type = "baseline"
        elif in_current and in_previous:
            change_type = "still_open"
        elif in_current:
            change_type = "new_review"
        else:
            change_type = "resolved"
        rows.append(
            {
                "match_id": match_id,
                "team_key": profile.team_key,
                "severity": key[0],
                "check_name": key[1],
                "finding_type": key[2],
                "athlete_name": key[3],
                "discipline": key[4],
                "stage_name": key[5],
                "previous_status": "OPEN" if in_previous else "",
                "current_status": "OPEN" if in_current else "RESOLVED",
                "change_type": change_type,
                "message": key[6],
                "notes": (
                    "First snapshot."
                    if change_type == "baseline"
                    else ""
                ),
            }
        )
    return rows


def _daily_brief(
    match_id: int,
    profile: TeamProfile,
    comparison_status: str,
    data_status: str,
    status_notes: list[str],
    athlete_changes: list[dict[str, Any]],
    award_changes: list[dict[str, Any]],
    squad_changes: list[dict[str, Any]],
    review_changes: list[dict[str, Any]],
    validation_counts: dict[str, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(
        section: str,
        priority: str,
        title: str,
        detail: str,
        *,
        athlete: str = "",
        discipline: str = "",
        squad: str = "",
        notes: str = "",
    ) -> None:
        rows.append(
            {
                "match_id": match_id,
                "team_key": profile.team_key,
                "brief_section": section,
                "priority": priority,
                "title": title,
                "detail": detail,
                "related_athlete": athlete,
                "related_discipline": discipline,
                "related_squad": squad,
                "notes": notes,
            }
        )

    status_priority = (
        "INFO" if data_status == "complete" else "HIGH"
    )
    add(
        "Data Status",
        status_priority,
        f"Current data status: {data_status}",
        " ".join(status_notes)
        or "Current Wilco data appears complete.",
    )
    add(
        "Data Status",
        "INFO",
        f"Comparison status: {comparison_status}",
        (
            "This run establishes the comparison baseline."
            if comparison_status == "BASELINE"
            else "Current results were compared with the prior snapshot."
            if comparison_status == "COMPARED"
            else "Prior snapshot files could not be compared safely."
        ),
    )

    changed_awards = [
        row
        for row in award_changes
        if row["change_type"] not in {"unchanged", "baseline"}
    ]
    if changed_awards:
        for row in changed_awards[:10]:
            add(
                "Awards",
                "HIGH",
                f"{row['athlete_name']} award position changed",
                (
                    f"{row['discipline']} {row['rank_scope']}: "
                    f"{row['previous_place'] or 'not listed'} → "
                    f"{row['current_place'] or 'not listed'}."
                ),
                athlete=row["athlete_name"],
                discipline=row["discipline"],
            )
    else:
        add(
            "Awards",
            "INFO",
            "No award-position changes detected",
            (
                "Award data is not available yet."
                if not award_changes and data_status != "complete"
                else "No Wilco award placement changed."
            ),
        )

    changed_athletes = [
        row
        for row in athlete_changes
        if row["change_type"]
        not in {"unchanged", "baseline", "incomplete"}
    ]
    if changed_athletes:
        for row in changed_athletes[:12]:
            add(
                "Athlete Changes",
                "MEDIUM",
                f"{row['athlete_name']}: {row['change_type']}",
                (
                    f"{row['discipline']} score "
                    f"{row['previous_score_seconds'] or 'pending'} → "
                    f"{row['current_score_seconds'] or 'pending'}; "
                    f"best place "
                    f"{row['previous_best_place'] or 'pending'} → "
                    f"{row['current_best_place'] or 'pending'}."
                ),
                athlete=row["athlete_name"],
                discipline=row["discipline"],
            )
    else:
        add(
            "Athlete Changes",
            "INFO",
            "No completed athlete-result changes detected",
            "Pending entries remain visible in the detailed change table.",
        )

    changed_squads = [
        row
        for row in squad_changes
        if row["change_type"] not in {"unchanged", "baseline"}
    ]
    if changed_squads:
        for row in changed_squads[:10]:
            add(
                "Squad Changes",
                "MEDIUM",
                f"{row['squad_name']}: {row['change_type']}",
                (
                    f"{row['discipline']} place "
                    f"{row['previous_squad_place'] or 'pending'} → "
                    f"{row['current_squad_place'] or 'pending'}."
                ),
                discipline=row["discipline"],
                squad=row["squad_name"],
            )
    else:
        add(
            "Squad Changes",
            "INFO",
            "No squad-result changes detected",
            "No Wilco squad placement or score changed.",
        )

    new_reviews = [
        row
        for row in review_changes
        if row["change_type"] == "new_review"
    ]
    resolved_reviews = [
        row
        for row in review_changes
        if row["change_type"] == "resolved"
    ]
    add(
        "Coach Review",
        "HIGH" if new_reviews else "INFO",
        f"{len(new_reviews)} new coach review item(s)",
        (
            f"{len(resolved_reviews)} prior item(s) resolved. "
            "Open details are listed on Review Changes."
        ),
    )

    add(
        "Validation",
        "HIGH" if validation_counts["ERROR"] else "MEDIUM",
        "Validation findings",
        (
            f"{validation_counts['ERROR']} error(s), "
            f"{validation_counts['WARNING']} warning(s), and "
            f"{validation_counts['REVIEW']} review item(s)."
        ),
    )
    action = (
        "Refresh again after additional scores or rankings post."
        if data_status != "complete"
        else "Review changed results and new coach items before sharing."
    )
    add(
        "Next Actions",
        "HIGH" if data_status != "complete" else "MEDIUM",
        "Recommended next action",
        action,
    )
    return rows


def _find_previous_snapshot(
    snapshots_dir: Path,
    team_key: str,
) -> Path | None:
    if not snapshots_dir.exists():
        return None
    candidates = [
        path
        for path in snapshots_dir.iterdir()
        if path.is_dir()
        and f"_{team_key}_" in path.name
        and (
            path
            / "team_report_tables"
            / team_key
        ).exists()
    ]
    return max(candidates, key=lambda path: path.name) if candidates else None


def _unique_snapshot_path(
    snapshots_dir: Path,
    timestamp: str,
    team_key: str,
    label: str,
) -> Path:
    base = snapshots_dir / f"{timestamp}_{team_key}_{label}"
    candidate = base
    counter = 2
    while candidate.exists():
        candidate = snapshots_dir / f"{base.name}_{counter}"
        counter += 1
    return candidate


def _preserve_snapshot(output_path: Path, snapshot_path: Path) -> None:
    try:
        snapshot_path.mkdir(parents=True, exist_ok=False)
        for name in SNAPSHOT_ITEMS:
            source = output_path / name
            if not source.exists():
                continue
            destination = snapshot_path / name
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
    except OSError as exc:
        raise NationalsOpsError(
            f"Could not preserve snapshot {snapshot_path}: {exc}"
        ) from exc


def _artifact_hashes(
    output_path: Path,
    profile: TeamProfile,
) -> dict[str, str]:
    raw_dir = output_path / "raw"
    match_id = output_path.name
    team_dir = (
        output_path / "team_report_tables" / profile.team_key
    )
    workbook = (
        output_path
        / "workbooks"
        / f"match_{match_id}_{profile.team_key}_report.xlsx"
    )
    return {
        "raw_slots_hash": _file_hash(
            raw_dir / f"{match_id}_slots.json"
        ),
        "raw_leaderboard_hash": _file_hash(
            raw_dir / f"{match_id}_leaderboard.json"
        ),
        "raw_schedule_hash": _file_hash(
            raw_dir / f"{match_id}_schedule.json"
        ),
        "team_report_hash": _directory_hash(team_dir),
        "workbook_hash": _file_hash(workbook),
    }


def _append_manifest(path: Path, row: dict[str, Any]) -> None:
    rows = _read_csv(path) if path.exists() else []
    rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(path, MANIFEST_COLUMNS, rows)


def _file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _directory_hash(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        return ""
    for file_path in files:
        digest.update(str(file_path.relative_to(path)).encode("utf-8"))
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _index_rows(
    rows: Iterable[dict[str, str]],
    key_fields: Iterable[str],
) -> dict[tuple[str, ...], dict[str, str]]:
    return {
        tuple(row.get(field, "") for field in key_fields): row
        for row in rows
    }


def _placement_change_type(
    current_row: dict[str, str] | None,
    previous_row: dict[str, str] | None,
    current_place: int | None,
    previous_place: int | None,
    baseline: bool,
) -> str:
    if baseline:
        return "baseline"
    if current_row is None:
        return "removed_or_missing"
    if previous_row is None:
        return "new_award"
    if current_place != previous_place:
        return "place_changed"
    return "unchanged"


def _score_place_change_type(
    current_row: dict[str, str] | None,
    previous_row: dict[str, str] | None,
    current_score: float | None,
    previous_score: float | None,
    current_place: int | None,
    previous_place: int | None,
    baseline: bool,
) -> str:
    if baseline:
        return "baseline"
    if current_row is None:
        return "removed_or_missing"
    if previous_row is None:
        return "new_score" if current_score is not None else "incomplete"
    if current_score is None:
        return "incomplete"
    if not _same_number(current_score, previous_score):
        return "score_changed"
    if current_place != previous_place:
        return "place_changed"
    return "unchanged"


def _simple_score_change_type(
    current_row: dict[str, str] | None,
    previous_row: dict[str, str] | None,
    current_score: float | None,
    previous_score: float | None,
    baseline: bool,
) -> str:
    if baseline:
        return "baseline"
    if current_row is None:
        return "removed_or_missing"
    if previous_row is None:
        return "new_score" if current_score is not None else "incomplete"
    if current_score is None:
        return "incomplete"
    if not _same_number(current_score, previous_score):
        return "score_changed"
    return "unchanged"


def _placement_note(change_type: str) -> str:
    return {
        "baseline": "First snapshot for this match and team.",
        "new_award": "New award/highlight row.",
        "new_score": "New scored result.",
        "score_changed": "Score changed from the prior snapshot.",
        "place_changed": "Placement changed from the prior snapshot.",
        "removed_or_missing": "Result is absent from current data.",
        "incomplete": "Current result is incomplete.",
    }.get(change_type, "")


def _changed_count(rows: Iterable[dict[str, Any]]) -> int:
    return sum(
        row.get("change_type")
        not in {"unchanged", "baseline", "incomplete", "still_open"}
        for row in rows
    )


def _summary_integer(
    source: dict[str, Any] | None,
    column: str,
) -> int:
    if not source:
        return 0
    return _integer(
        source.get("summary_row", {}).get(column)
    ) or 0


def _same_number(
    left: float | int | None,
    right: float | int | None,
) -> bool:
    if left is None or right is None:
        return left is right
    return abs(float(left) - float(right)) <= 0.001


def _difference(
    current: float | int | None,
    previous: float | int | None,
) -> float | int | str:
    if current is None or previous is None:
        return ""
    value = float(current) - float(previous)
    rounded = round(value, 3)
    return int(rounded) if rounded.is_integer() else rounded


def _display(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        rounded = round(value, 3)
        return int(rounded) if rounded.is_integer() else rounded
    return value


def _number(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
    return cleaned.strip("-_") or "manual"


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            return list(csv.DictReader(source))
    except (OSError, csv.Error) as exc:
        raise NationalsOpsError(f"Could not read {path}: {exc}") from exc


def _write_csv(
    path: Path,
    columns: Iterable[str],
    rows: Iterable[dict[str, Any]],
) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(
                target,
                fieldnames=columns,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, csv.Error) as exc:
        raise NationalsOpsError(f"Could not write {path}: {exc}") from exc
