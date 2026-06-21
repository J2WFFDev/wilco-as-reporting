"""Read-only inventory of locally downloaded raw SASP JSON files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from wilco_as_reporting.raw_content import (
    JsonContentStatus,
    inspect_json_file,
)

LOCAL_INVENTORY_COLUMNS = (
    "match_id",
    "file_type",
    "file_path",
    "file_exists",
    "file_size_bytes",
    "modified_time",
    "json_valid",
    "json_kind",
    "json_empty",
    "useful_content",
    "content_issue",
    "notes",
)

COVERAGE_COLUMNS = (
    "match_id",
    "has_slots",
    "has_leaderboard",
    "has_schedule",
    "slots_useful_content",
    "leaderboard_useful_content",
    "schedule_useful_content",
    "core_complete",
    "schedule_complete",
    "missing_files",
    "content_issues",
    "notes",
)

MISSING_COLUMNS = (
    "match_id",
    "missing_slots",
    "missing_leaderboard",
    "missing_schedule",
    "slots_useful_content",
    "leaderboard_useful_content",
    "schedule_useful_content",
    "core_complete",
    "recommended_download",
    "content_issue",
    "notes",
)

CONTENT_ISSUE_COLUMNS = (
    "match_id",
    "endpoint_type",
    "file_path",
    "file_size_bytes",
    "json_valid",
    "json_kind",
    "useful_content",
    "issue_type",
    "issue_message",
)

SUMMARY_COLUMNS = (
    "total_matches_checked",
    "total_files_checked",
    "useful_files_count",
    "no_content_files_count",
    "invalid_files_count",
    "core_complete_count",
    "incomplete_match_count",
    "missing_slots_count",
    "missing_leaderboard_count",
    "missing_schedule_count",
    "schedule_required",
    "notes",
)

FILE_TYPES = ("slots", "leaderboard", "schedule")


class RawInventoryError(RuntimeError):
    """Raised when inventory inputs or outputs cannot be processed."""


@dataclass(frozen=True)
class RawInventoryResult:
    local_inventory_path: Path
    coverage_path: Path
    missing_path: Path
    content_issues_path: Path
    summary_path: Path
    total_matches: int
    total_files: int
    useful_files_count: int
    no_content_files_count: int
    invalid_files_count: int
    core_complete_count: int
    incomplete_match_count: int
    missing_slots_count: int
    missing_leaderboard_count: int
    missing_schedule_count: int


def build_raw_inventory(
    *,
    output_root: Path | str,
    match_index: Path | str | None = None,
    match_ids: tuple[int, ...] = (),
    require_schedule: bool = False,
    team_key: str = "",
) -> RawInventoryResult:
    """Scan local raw folders and write coverage tables without API calls."""
    output_path = Path(output_root)
    selected_ids = _select_match_ids(
        output_path,
        Path(match_index) if match_index else None,
        match_ids,
    )
    inventory_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []

    for match_id in selected_ids:
        paths = {
            file_type: (
                output_path
                / str(match_id)
                / "raw"
                / f"{match_id}_{file_type}.json"
            )
            for file_type in FILE_TYPES
        }
        states = {
            file_type: inspect_json_file(path)
            for file_type, path in paths.items()
        }
        for file_type in FILE_TYPES:
            state = states[file_type]
            inventory_rows.append(
                _inventory_row(
                    match_id,
                    file_type,
                    paths[file_type],
                    state,
                )
            )
            if not state.useful_content:
                issue_rows.append(
                    _issue_row(
                        match_id,
                        file_type,
                        paths[file_type],
                        state,
                    )
                )

        slots = states["slots"]
        leaderboard = states["leaderboard"]
        schedule = states["schedule"]
        core_complete = (
            slots.useful_content and leaderboard.useful_content
        )
        schedule_complete = schedule.useful_content
        missing_files = [
            paths[file_type].name
            for file_type in FILE_TYPES
            if not states[file_type].file_exists
        ]
        content_issues = [
            f"{file_type}:{states[file_type].issue_type}"
            for file_type in FILE_TYPES
            if states[file_type].issue_type
        ]
        notes: list[str] = []
        if (
            core_complete
            and not schedule_complete
            and not require_schedule
        ):
            notes.append(
                "Core JSON is complete; schedule content is optional."
            )
        if require_schedule and not schedule_complete:
            notes.append(
                "Useful schedule content is required for this run."
            )
        if team_key:
            notes.append(
                f"Team key {team_key!r} is informational; raw coverage "
                "is match-level."
            )
        coverage_rows.append(
            {
                "match_id": match_id,
                "has_slots": _boolean(slots.file_exists),
                "has_leaderboard": _boolean(
                    leaderboard.file_exists
                ),
                "has_schedule": _boolean(schedule.file_exists),
                "slots_useful_content": _boolean(
                    slots.useful_content
                ),
                "leaderboard_useful_content": _boolean(
                    leaderboard.useful_content
                ),
                "schedule_useful_content": _boolean(
                    schedule.useful_content
                ),
                "core_complete": _boolean(core_complete),
                "schedule_complete": _boolean(schedule_complete),
                "missing_files": ";".join(missing_files),
                "content_issues": ";".join(content_issues),
                "notes": " ".join(notes),
            }
        )

        match_complete = core_complete and (
            schedule_complete or not require_schedule
        )
        if not match_complete:
            recommended = [
                file_type
                for file_type in FILE_TYPES
                if (
                    not states[file_type].useful_content
                    and (
                        file_type != "schedule"
                        or require_schedule
                    )
                )
            ]
            missing_rows.append(
                {
                    "match_id": match_id,
                    "missing_slots": _boolean(
                        not slots.file_exists
                    ),
                    "missing_leaderboard": _boolean(
                        not leaderboard.file_exists
                    ),
                    "missing_schedule": _boolean(
                        not schedule.file_exists
                    ),
                    "slots_useful_content": _boolean(
                        slots.useful_content
                    ),
                    "leaderboard_useful_content": _boolean(
                        leaderboard.useful_content
                    ),
                    "schedule_useful_content": _boolean(
                        schedule.useful_content
                    ),
                    "core_complete": _boolean(core_complete),
                    "recommended_download": ",".join(recommended),
                    "content_issue": ";".join(content_issues),
                    "notes": (
                        "Existing no-content files are reported but are "
                        "not automatically re-downloaded."
                    ),
                }
            )

    total_files = len(inventory_rows)
    useful_files = sum(
        row["useful_content"] == "true" for row in inventory_rows
    )
    invalid_files = sum(
        row["json_kind"] == "invalid" for row in inventory_rows
    )
    no_content_files = total_files - useful_files - invalid_files
    core_complete_count = sum(
        row["core_complete"] == "true" for row in coverage_rows
    )
    incomplete_count = sum(
        not (
            row["core_complete"] == "true"
            and (
                row["schedule_complete"] == "true"
                or not require_schedule
            )
        )
        for row in coverage_rows
    )
    summary = {
        "total_matches_checked": len(selected_ids),
        "total_files_checked": total_files,
        "useful_files_count": useful_files,
        "no_content_files_count": no_content_files,
        "invalid_files_count": invalid_files,
        "core_complete_count": core_complete_count,
        "incomplete_match_count": incomplete_count,
        "missing_slots_count": sum(
            row["has_slots"] == "false" for row in coverage_rows
        ),
        "missing_leaderboard_count": sum(
            row["has_leaderboard"] == "false"
            for row in coverage_rows
        ),
        "missing_schedule_count": sum(
            row["has_schedule"] == "false"
            for row in coverage_rows
        ),
        "schedule_required": _boolean(require_schedule),
        "notes": (
            "Core completeness requires useful slots and leaderboard "
            "content. Schedule is optional."
            if not require_schedule
            else "Useful slots, leaderboard, and schedule content are "
            "required."
        ),
    }
    inventory_dir = output_path / "inventory"
    local_inventory_path = inventory_dir / "local_raw_inventory.csv"
    coverage_path = inventory_dir / "raw_file_coverage.csv"
    missing_path = inventory_dir / "missing_core_json.csv"
    content_issues_path = inventory_dir / "raw_content_issues.csv"
    summary_path = inventory_dir / "raw_status_summary.csv"
    _write_csv(
        local_inventory_path,
        LOCAL_INVENTORY_COLUMNS,
        inventory_rows,
    )
    _write_csv(coverage_path, COVERAGE_COLUMNS, coverage_rows)
    _write_csv(missing_path, MISSING_COLUMNS, missing_rows)
    _write_csv(
        content_issues_path,
        CONTENT_ISSUE_COLUMNS,
        issue_rows,
    )
    _write_csv(summary_path, SUMMARY_COLUMNS, [summary])
    return RawInventoryResult(
        local_inventory_path=local_inventory_path,
        coverage_path=coverage_path,
        missing_path=missing_path,
        content_issues_path=content_issues_path,
        summary_path=summary_path,
        total_matches=summary["total_matches_checked"],
        total_files=summary["total_files_checked"],
        useful_files_count=summary["useful_files_count"],
        no_content_files_count=summary["no_content_files_count"],
        invalid_files_count=summary["invalid_files_count"],
        core_complete_count=summary["core_complete_count"],
        incomplete_match_count=summary["incomplete_match_count"],
        missing_slots_count=summary["missing_slots_count"],
        missing_leaderboard_count=summary[
            "missing_leaderboard_count"
        ],
        missing_schedule_count=summary["missing_schedule_count"],
    )


def _inventory_row(
    match_id: int,
    file_type: str,
    path: Path,
    state: JsonContentStatus,
) -> dict[str, Any]:
    modified_time = ""
    if state.file_exists:
        try:
            modified_time = (
                datetime.fromtimestamp(path.stat().st_mtime)
                .astimezone()
                .isoformat(timespec="seconds")
            )
        except OSError:
            modified_time = ""
    return {
        "match_id": match_id,
        "file_type": file_type,
        "file_path": str(path),
        "file_exists": _boolean(state.file_exists),
        "file_size_bytes": state.file_size_bytes,
        "modified_time": modified_time,
        "json_valid": _boolean(state.json_valid),
        "json_kind": state.json_kind,
        "json_empty": _boolean(state.json_empty),
        "useful_content": _boolean(state.useful_content),
        "content_issue": state.content_issue,
        "notes": "",
    }


def _issue_row(
    match_id: int,
    file_type: str,
    path: Path,
    state: JsonContentStatus,
) -> dict[str, Any]:
    return {
        "match_id": match_id,
        "endpoint_type": file_type,
        "file_path": str(path),
        "file_size_bytes": state.file_size_bytes,
        "json_valid": _boolean(state.json_valid),
        "json_kind": state.json_kind,
        "useful_content": _boolean(state.useful_content),
        "issue_type": state.issue_type or "no_useful_content",
        "issue_message": (
            state.content_issue
            or "JSON file contains no useful SASP endpoint content."
        ),
    }


def _select_match_ids(
    output_root: Path,
    match_index: Path | None,
    match_ids: tuple[int, ...],
) -> tuple[int, ...]:
    if match_ids:
        return tuple(sorted(set(match_ids)))
    if match_index:
        rows = _read_csv(match_index)
        selected = {
            _parse_match_id(row.get("match_id", ""), match_index)
            for row in rows
        }
        return tuple(sorted(selected))
    if not output_root.exists():
        return ()
    inferred = {
        int(child.name)
        for child in output_root.iterdir()
        if child.is_dir()
        and child.name.isdigit()
        and (child / "raw").is_dir()
    }
    return tuple(sorted(inferred))


def _parse_match_id(value: str, path: Path) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise RawInventoryError(
            f"Invalid match_id {value!r} in {path}."
        ) from exc


def _boolean(value: bool) -> str:
    return str(bool(value)).lower()


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames or "match_id" not in reader.fieldnames:
                raise RawInventoryError(
                    f"Match index must contain match_id: {path}"
                )
            return list(reader)
    except FileNotFoundError as exc:
        raise RawInventoryError(
            f"Match index does not exist: {path}"
        ) from exc
    except (OSError, csv.Error) as exc:
        raise RawInventoryError(
            f"Could not read match index {path}: {exc}"
        ) from exc


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
        raise RawInventoryError(f"Could not write {path}: {exc}") from exc
