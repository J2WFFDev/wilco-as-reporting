"""Read-only inventory of locally downloaded raw SASP JSON files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

LOCAL_INVENTORY_COLUMNS = (
    "match_id",
    "file_type",
    "file_path",
    "file_exists",
    "file_size_bytes",
    "modified_time",
    "notes",
)

COVERAGE_COLUMNS = (
    "match_id",
    "has_slots",
    "has_leaderboard",
    "has_schedule",
    "core_complete",
    "schedule_complete",
    "missing_files",
    "notes",
)

MISSING_COLUMNS = (
    "match_id",
    "missing_slots",
    "missing_leaderboard",
    "missing_schedule",
    "recommended_download",
    "notes",
)

SUMMARY_COLUMNS = (
    "total_matches_checked",
    "core_complete_count",
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
    summary_path: Path
    total_matches: int
    core_complete_count: int
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

    for match_id in selected_ids:
        states = {
            file_type: _file_state(
                output_path
                / str(match_id)
                / "raw"
                / f"{match_id}_{file_type}.json"
            )
            for file_type in FILE_TYPES
        }
        for file_type in FILE_TYPES:
            state = states[file_type]
            inventory_rows.append(
                {
                    "match_id": match_id,
                    "file_type": file_type,
                    "file_path": str(state["path"]),
                    "file_exists": _boolean(state["exists"]),
                    "file_size_bytes": state["size"],
                    "modified_time": state["modified_time"],
                    "notes": (
                        ""
                        if state["exists"]
                        else "Expected local raw JSON file is missing."
                    ),
                }
            )

        has_slots = states["slots"]["exists"]
        has_leaderboard = states["leaderboard"]["exists"]
        has_schedule = states["schedule"]["exists"]
        core_complete = has_slots and has_leaderboard
        schedule_complete = has_schedule
        missing_files = [
            f"{match_id}_{file_type}.json"
            for file_type in FILE_TYPES
            if not states[file_type]["exists"]
        ]
        notes: list[str] = []
        if core_complete and not has_schedule and not require_schedule:
            notes.append("Core JSON is complete; schedule is optional.")
        if require_schedule and not has_schedule:
            notes.append("Schedule is required for this inventory run.")
        if team_key:
            notes.append(
                f"Team key {team_key!r} is informational; raw coverage "
                "is match-level."
            )
        coverage_rows.append(
            {
                "match_id": match_id,
                "has_slots": _boolean(has_slots),
                "has_leaderboard": _boolean(has_leaderboard),
                "has_schedule": _boolean(has_schedule),
                "core_complete": _boolean(core_complete),
                "schedule_complete": _boolean(schedule_complete),
                "missing_files": ";".join(missing_files),
                "notes": " ".join(notes),
            }
        )

        if not core_complete or (require_schedule and not has_schedule):
            recommended = [
                file_type
                for file_type in FILE_TYPES
                if (
                    not states[file_type]["exists"]
                    and (
                        file_type != "schedule"
                        or require_schedule
                    )
                )
            ]
            missing_rows.append(
                {
                    "match_id": match_id,
                    "missing_slots": _boolean(not has_slots),
                    "missing_leaderboard": _boolean(
                        not has_leaderboard
                    ),
                    "missing_schedule": _boolean(not has_schedule),
                    "recommended_download": ",".join(recommended),
                    "notes": (
                        "Download only the listed missing endpoint types."
                    ),
                }
            )

    summary = {
        "total_matches_checked": len(selected_ids),
        "core_complete_count": sum(
            row["core_complete"] == "true"
            for row in coverage_rows
        ),
        "missing_slots_count": sum(
            row["has_slots"] == "false"
            for row in coverage_rows
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
            "Schedule absence does not make core JSON incomplete."
            if not require_schedule
            else "Slots, leaderboard, and schedule are required."
        ),
    }
    inventory_dir = output_path / "inventory"
    local_inventory_path = inventory_dir / "local_raw_inventory.csv"
    coverage_path = inventory_dir / "raw_file_coverage.csv"
    missing_path = inventory_dir / "missing_core_json.csv"
    summary_path = inventory_dir / "raw_status_summary.csv"
    _write_csv(
        local_inventory_path,
        LOCAL_INVENTORY_COLUMNS,
        inventory_rows,
    )
    _write_csv(coverage_path, COVERAGE_COLUMNS, coverage_rows)
    _write_csv(missing_path, MISSING_COLUMNS, missing_rows)
    _write_csv(summary_path, SUMMARY_COLUMNS, [summary])
    return RawInventoryResult(
        local_inventory_path=local_inventory_path,
        coverage_path=coverage_path,
        missing_path=missing_path,
        summary_path=summary_path,
        total_matches=summary["total_matches_checked"],
        core_complete_count=summary["core_complete_count"],
        missing_slots_count=summary["missing_slots_count"],
        missing_leaderboard_count=summary[
            "missing_leaderboard_count"
        ],
        missing_schedule_count=summary["missing_schedule_count"],
    )


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


def _file_state(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {
            "path": path,
            "exists": False,
            "size": 0,
            "modified_time": "",
        }
    except OSError as exc:
        raise RawInventoryError(
            f"Could not inspect raw file {path}: {exc}"
        ) from exc
    return {
        "path": path,
        "exists": path.is_file(),
        "size": stat.st_size if path.is_file() else 0,
        "modified_time": (
            datetime.fromtimestamp(stat.st_mtime)
            .astimezone()
            .isoformat(timespec="seconds")
            if path.is_file()
            else ""
        ),
    }


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
