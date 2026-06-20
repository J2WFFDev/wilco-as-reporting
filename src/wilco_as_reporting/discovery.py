"""Discover SASP competitions and build curated match indexes."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from wilco_as_reporting.api.sasp_client import SaspClient, SnapshotWriteError

EXCLUSION_TERMS = (
    "test",
    "practice",
    "demo",
    "sample",
    "copy",
    "do not use",
)

MATCH_INDEX_COLUMNS = (
    "match_id",
    "name",
    "start_date",
    "end_date",
    "open_date",
    "close_date",
    "post_raw",
    "post",
    "type",
    "status",
    "notes",
    "stage_one",
    "stage_two",
    "stage_three",
    "stage_four",
    "shooting_style",
    "classification_id",
    "classification_value",
    "classification_descr",
    "classification_alt",
    "registration_type_id",
    "registration_type_value",
    "registration_type_descr",
    "host_entity_id",
    "host_team_name",
    "host_state",
    "host_state_abbr",
    "range_id",
    "range_name",
    "range_city",
    "range_state_id",
    "range_zip",
    "create_date",
    "update_date",
)

EFFECTIVE_INDEX_COLUMNS = MATCH_INDEX_COLUMNS + (
    "override_label",
    "override_notes",
    "selection_reason",
)


@dataclass(frozen=True)
class MatchOverride:
    match_id: int
    force_include: bool
    force_exclude: bool
    label: str
    notes: str


@dataclass(frozen=True)
class DiscoveryResult:
    pages_processed: int
    matches_discovered: int
    matches_included: int
    match_index_path: Path
    effective_match_index_path: Path


def discover_matches(
    client: SaspClient,
    output_dir: Path | str,
    overrides_path: Path | str,
    *,
    overwrite: bool = False,
) -> DiscoveryResult:
    """Fetch competition pages and write raw and curated match indexes."""
    output_path = Path(output_dir)
    raw_dir = output_path / "raw"
    tables_dir = output_path / "tables"
    _ensure_directory(raw_dir)
    _ensure_directory(tables_dir)

    competitions: list[dict[str, Any]] = []
    page = 1
    pages_processed = 0

    while True:
        snapshot_path = raw_dir / f"competitions_page_{page}.json"
        payload = _load_or_fetch_page(
            client,
            page,
            snapshot_path,
            overwrite=overwrite,
        )
        page_rows = _competition_rows(payload, page)
        competitions.extend(page_rows)
        pages_processed += 1

        if not page_rows or _is_last_page(payload, page):
            break
        page += 1

    match_rows = [_flatten_competition(row) for row in competitions]
    match_rows.sort(key=lambda row: _match_sort_key(row["match_id"]))

    match_index_path = tables_dir / "match_index.csv"
    _write_csv(match_index_path, MATCH_INDEX_COLUMNS, match_rows)

    overrides = load_match_overrides(overrides_path)
    effective_rows = build_effective_match_index(match_rows, overrides)
    effective_match_index_path = tables_dir / "effective_match_index.csv"
    _write_csv(
        effective_match_index_path,
        EFFECTIVE_INDEX_COLUMNS,
        effective_rows,
    )

    return DiscoveryResult(
        pages_processed=pages_processed,
        matches_discovered=len(match_rows),
        matches_included=len(effective_rows),
        match_index_path=match_index_path,
        effective_match_index_path=effective_match_index_path,
    )


def load_match_overrides(
    overrides_path: Path | str,
) -> dict[int, MatchOverride]:
    """Load curated include and exclude decisions keyed by match ID."""
    path = Path(overrides_path)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            required = {
                "match_id",
                "force_include",
                "force_exclude",
                "label",
                "notes",
            }
            if reader.fieldnames is None or not required.issubset(
                reader.fieldnames
            ):
                raise ValueError(
                    f"Override file must contain columns: "
                    f"{', '.join(sorted(required))}"
                )

            overrides: dict[int, MatchOverride] = {}
            for line_number, row in enumerate(reader, start=2):
                match_id = _parse_match_id(row["match_id"], line_number)
                override = MatchOverride(
                    match_id=match_id,
                    force_include=_parse_bool(
                        row["force_include"],
                        "force_include",
                        line_number,
                    ),
                    force_exclude=_parse_bool(
                        row["force_exclude"],
                        "force_exclude",
                        line_number,
                    ),
                    label=(row["label"] or "").strip(),
                    notes=(row["notes"] or "").strip(),
                )
                if override.force_include and override.force_exclude:
                    raise ValueError(
                        f"Override line {line_number} cannot force both "
                        "include and exclude."
                    )
                if match_id in overrides:
                    raise ValueError(
                        f"Duplicate match_id {match_id} on override line "
                        f"{line_number}."
                    )
                overrides[match_id] = override
    except OSError as exc:
        raise SnapshotWriteError(
            f"Could not read match overrides {path}: {exc}"
        ) from exc

    return overrides


def build_effective_match_index(
    match_rows: Iterable[dict[str, Any]],
    overrides: dict[int, MatchOverride],
) -> list[dict[str, Any]]:
    """Apply automatic filtering and curated overrides to discovered matches."""
    effective_rows: list[dict[str, Any]] = []

    for match in match_rows:
        match_id = int(match["match_id"])
        override = overrides.get(match_id)
        automatic_exclusion = _automatic_exclusion_reason(
            str(match.get("name") or "")
        )

        if override and override.force_exclude:
            continue
        if automatic_exclusion and not (
            override and override.force_include
        ):
            continue

        effective = dict(match)
        effective["override_label"] = override.label if override else ""
        effective["override_notes"] = override.notes if override else ""
        if override and override.force_include:
            effective["selection_reason"] = "force_include"
        else:
            effective["selection_reason"] = "discovered"
        effective_rows.append(effective)

    return effective_rows


def _load_or_fetch_page(
    client: SaspClient,
    page: int,
    snapshot_path: Path,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    if snapshot_path.exists() and not overwrite:
        try:
            with snapshot_path.open("r", encoding="utf-8") as snapshot:
                payload = json.load(snapshot)
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotWriteError(
                f"Could not read raw discovery snapshot "
                f"{snapshot_path}: {exc}"
            ) from exc
    else:
        payload = client.fetch_competitions_page(page)
        _write_json(snapshot_path, payload)

    if not isinstance(payload, dict):
        raise SnapshotWriteError(
            f"Competition page {page} must be a JSON object."
        )
    return payload


def _competition_rows(
    payload: dict[str, Any],
    page: int,
) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise SnapshotWriteError(
            f"Competition page {page} is missing a data list."
        )
    if not all(isinstance(row, dict) for row in data):
        raise SnapshotWriteError(
            f"Competition page {page} contains a non-object data row."
        )
    return data


def _is_last_page(payload: dict[str, Any], page: int) -> bool:
    meta = payload.get("meta")
    if isinstance(meta, dict):
        last_page = meta.get("last_page")
        if isinstance(last_page, int):
            return page >= last_page

    links = payload.get("links")
    if isinstance(links, dict) and "next" in links:
        return not bool(links.get("next"))

    return False


def _flatten_competition(match: dict[str, Any]) -> dict[str, Any]:
    classification = _mapping(match.get("classification"))
    registration_type = _mapping(match.get("registration_type"))
    hosting_team = _mapping(match.get("hosting_team"))
    host_state = _mapping(hosting_team.get("state"))
    match_range = _mapping(match.get("range"))

    return {
        "match_id": match.get("id"),
        "name": match.get("name"),
        "start_date": match.get("start_date"),
        "end_date": match.get("end_date"),
        "open_date": match.get("open_date"),
        "close_date": match.get("close_date"),
        "post_raw": match.get("post_raw"),
        "post": match.get("post"),
        "type": match.get("type"),
        "status": match.get("status"),
        "notes": match.get("note"),
        "stage_one": match.get("stage_one"),
        "stage_two": match.get("stage_two"),
        "stage_three": match.get("stage_three"),
        "stage_four": match.get("stage_four"),
        "shooting_style": match.get("shooting_style"),
        "classification_id": classification.get("id"),
        "classification_value": classification.get("value"),
        "classification_descr": classification.get("descr"),
        "classification_alt": classification.get("alt"),
        "registration_type_id": registration_type.get("id"),
        "registration_type_value": registration_type.get("value"),
        "registration_type_descr": registration_type.get("descr"),
        "host_entity_id": match.get("host_ent_id"),
        "host_team_name": hosting_team.get("name"),
        "host_state": host_state.get("name"),
        "host_state_abbr": host_state.get("abbr"),
        "range_id": match.get("range_id"),
        "range_name": match_range.get("name"),
        "range_city": match_range.get("pcity"),
        "range_state_id": match_range.get("pstate_id"),
        "range_zip": match_range.get("pzip"),
        "create_date": match.get("create_date"),
        "update_date": match.get("update_date"),
    }


def _automatic_exclusion_reason(name: str) -> str | None:
    normalized_name = re.sub(
        r"[^a-z0-9]+",
        " ",
        name.casefold(),
    ).strip()
    padded_name = f" {normalized_name} "
    for term in EXCLUSION_TERMS:
        if f" {term} " in padded_name:
            return f"name_contains_{term.replace(' ', '_')}"
    return None


def _write_json(path: Path, payload: Any) -> None:
    try:
        with path.open("w", encoding="utf-8") as target:
            json.dump(payload, target, indent=2, ensure_ascii=False)
            target.write("\n")
    except (OSError, TypeError, ValueError) as exc:
        raise SnapshotWriteError(
            f"Could not write raw discovery snapshot {path}: {exc}"
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
        raise SnapshotWriteError(
            f"Could not write match index {path}: {exc}"
        ) from exc


def _ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SnapshotWriteError(
            f"Could not create output directory {path}: {exc}"
        ) from exc
    if not path.is_dir():
        raise SnapshotWriteError(f"Output path is not a directory: {path}")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _match_sort_key(value: Any) -> tuple[int, str]:
    try:
        return (0, f"{int(value):020d}")
    except (TypeError, ValueError):
        return (1, str(value))


def _parse_match_id(value: str | None, line_number: int) -> int:
    try:
        return int((value or "").strip())
    except ValueError as exc:
        raise ValueError(
            f"Invalid match_id on override line {line_number}: {value!r}"
        ) from exc


def _parse_bool(
    value: str | None,
    field: str,
    line_number: int,
) -> bool:
    normalized = (value or "").strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(
        f"Invalid {field} on override line {line_number}: {value!r}"
    )
