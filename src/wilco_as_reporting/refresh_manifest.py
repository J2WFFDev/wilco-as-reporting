"""Shared runtime refresh manifest and artifact hashing helpers."""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

MANIFEST_COLUMNS = (
    "match_id",
    "team_key",
    "match_name",
    "last_checked_at",
    "last_changed_at",
    "last_success_at",
    "last_status",
    "last_data_status",
    "raw_slots_hash",
    "raw_leaderboard_hash",
    "raw_schedule_hash",
    "team_report_hash",
    "latest_snapshot_path",
    "latest_artifact_name",
    "validation_error_count",
    "validation_warning_count",
    "validation_review_count",
    "notes",
)


class RefreshManifestError(RuntimeError):
    """Raised when refresh state cannot be read or written."""


def load_manifest(path: Path | str) -> dict[tuple[str, str], dict[str, str]]:
    """Load the latest row per match and team, migrating older schemas."""
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {}
    try:
        with manifest_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as source:
            rows = list(csv.DictReader(source))
    except (OSError, csv.Error) as exc:
        raise RefreshManifestError(
            f"Could not read refresh manifest {manifest_path}: {exc}"
        ) from exc

    latest: dict[tuple[str, str], dict[str, str]] = {}
    for source_row in rows:
        row = _migrate_row(source_row)
        key = (row["match_id"], row["team_key"])
        current = latest.get(key)
        if current is None or _row_timestamp(row) >= _row_timestamp(current):
            latest[key] = row
    return latest


def update_manifest(
    path: Path | str,
    values: dict[str, Any],
) -> dict[str, str]:
    """Upsert current state for one match/team and write canonical columns."""
    manifest_path = Path(path)
    rows = load_manifest(manifest_path)
    match_id = str(values.get("match_id", "")).strip()
    team_key = str(values.get("team_key", "")).strip()
    if not match_id or not team_key:
        raise RefreshManifestError(
            "Manifest updates require match_id and team_key."
        )
    key = (match_id, team_key)
    row = dict(rows.get(key, _blank_row()))
    for column in MANIFEST_COLUMNS:
        if column in values:
            row[column] = _text(values[column])
    row["match_id"] = match_id
    row["team_key"] = team_key
    rows[key] = row
    _write_manifest(manifest_path, rows.values())
    return row


def file_hash(path: Path | str) -> str:
    """Return a SHA-256 file hash, or blank when the file is absent."""
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return ""
    digest = hashlib.sha256()
    try:
        with file_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def directory_hash(path: Path | str) -> str:
    """Return a stable combined hash for all files below a directory."""
    directory = Path(path)
    if not directory.exists():
        return ""
    files = sorted(item for item in directory.rglob("*") if item.is_file())
    if not files:
        return ""
    digest = hashlib.sha256()
    try:
        for file_path in files:
            digest.update(
                str(file_path.relative_to(directory)).encode("utf-8")
            )
            digest.update(file_path.read_bytes())
    except OSError:
        return ""
    return digest.hexdigest()


def raw_hashes(
    output_dir: Path | str,
    match_id: int,
) -> dict[str, str]:
    """Hash the three supported raw match snapshots."""
    raw_dir = Path(output_dir) / "raw"
    return {
        "raw_slots_hash": file_hash(
            raw_dir / f"{match_id}_slots.json"
        ),
        "raw_leaderboard_hash": file_hash(
            raw_dir / f"{match_id}_leaderboard.json"
        ),
        "raw_schedule_hash": file_hash(
            raw_dir / f"{match_id}_schedule.json"
        ),
    }


def combined_raw_hash(hashes: dict[str, str]) -> str:
    """Combine raw component hashes into one comparison value."""
    components = [
        hashes.get("raw_slots_hash", ""),
        hashes.get("raw_leaderboard_hash", ""),
        hashes.get("raw_schedule_hash", ""),
    ]
    if not any(components):
        return ""
    digest = hashlib.sha256()
    digest.update("|".join(components).encode("ascii"))
    return digest.hexdigest()


def utc_now() -> str:
    """Return a stable timezone-aware runtime timestamp."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _migrate_row(source: dict[str, str]) -> dict[str, str]:
    row = _blank_row()
    for column in MANIFEST_COLUMNS:
        if source.get(column) is not None:
            row[column] = source.get(column, "")
    run_timestamp = source.get("run_timestamp", "")
    row["last_checked_at"] = row["last_checked_at"] or run_timestamp
    row["last_success_at"] = row["last_success_at"] or run_timestamp
    row["last_changed_at"] = row["last_changed_at"] or run_timestamp
    row["last_status"] = row["last_status"] or (
        "SUCCESS" if run_timestamp else ""
    )
    row["last_data_status"] = (
        row["last_data_status"] or source.get("data_status", "")
    )
    row["latest_snapshot_path"] = (
        row["latest_snapshot_path"] or source.get("snapshot_path", "")
    )
    if source.get("snapshot_label"):
        label_note = f"Snapshot label: {source['snapshot_label']}."
        row["notes"] = " ".join(
            item
            for item in (row["notes"], label_note)
            if item
        )
    return row


def _row_timestamp(row: dict[str, str]) -> str:
    return (
        row.get("last_checked_at")
        or row.get("last_success_at")
        or row.get("last_changed_at")
        or ""
    )


def _blank_row() -> dict[str, str]:
    return {column: "" for column in MANIFEST_COLUMNS}


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _write_manifest(
    path: Path,
    rows: Iterable[dict[str, str]],
) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(
            rows,
            key=lambda row: (
                _numeric_sort(row.get("match_id", "")),
                row.get("team_key", ""),
            ),
        )
        with path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(
                target,
                fieldnames=MANIFEST_COLUMNS,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(ordered)
    except (OSError, csv.Error) as exc:
        raise RefreshManifestError(
            f"Could not write refresh manifest {path}: {exc}"
        ) from exc


def _numeric_sort(value: str) -> tuple[int, str]:
    try:
        return (0, f"{int(value):020d}")
    except ValueError:
        return (1, value)
