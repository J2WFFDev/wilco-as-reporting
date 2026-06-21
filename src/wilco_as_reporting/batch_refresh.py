"""Guarded historical backfill and incremental match refresh orchestration."""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from wilco_as_reporting.api.sasp_client import SaspApiError, SaspClient
from wilco_as_reporting.discovery import (
    MatchOverride,
    discover_matches,
    load_match_overrides,
)
from wilco_as_reporting.nationals_ops import NationalsOpsError
from wilco_as_reporting.parsers import MatchParseError, parse_match
from wilco_as_reporting.pipeline import build_nationals_match
from wilco_as_reporting.refresh_manifest import (
    RefreshManifestError,
    combined_raw_hash,
    directory_hash,
    load_manifest,
    raw_hashes,
    update_manifest,
    utc_now,
)
from wilco_as_reporting.reports import (
    MatchReportError,
    TeamReportError,
    build_match_report,
    build_team_report,
)
from wilco_as_reporting.team_profiles import TeamProfile
from wilco_as_reporting.validators import (
    MatchValidationError,
    validate_match,
)
from wilco_as_reporting.workbooks import (
    MatchWorkbookError,
    NationalsWorkbookError,
    TeamWorkbookError,
)

BUILD_LEVELS = ("raw", "parse", "validate", "report", "team", "nationals")

BACKFILL_PLAN_COLUMNS = (
    "match_id",
    "match_name",
    "start_date",
    "end_date",
    "post_raw",
    "selected_reason",
    "planned_build_level",
    "dry_run",
    "notes",
)

BACKFILL_RESULT_COLUMNS = (
    "match_id",
    "match_name",
    "build_level",
    "status",
    "data_status",
    "raw_changed",
    "parsed_rows",
    "validation_error_count",
    "validation_warning_count",
    "validation_review_count",
    "artifact_or_output_path",
    "elapsed_seconds",
    "notes",
)

BACKFILL_ERROR_COLUMNS = (
    "match_id",
    "match_name",
    "step",
    "error_type",
    "error_message",
    "notes",
)

INCREMENTAL_CANDIDATE_COLUMNS = (
    "match_id",
    "match_name",
    "start_date",
    "end_date",
    "post_raw",
    "candidate_reason",
    "watched",
    "active",
    "recent",
    "planned_build_level",
    "dry_run",
    "notes",
)

INCREMENTAL_RESULT_COLUMNS = (
    "match_id",
    "match_name",
    "status",
    "data_status",
    "changed",
    "previous_hash",
    "current_hash",
    "validation_error_count",
    "validation_warning_count",
    "validation_review_count",
    "output_path",
    "notes",
)

KNOWN_MATCHES = {
    628: "2025 SASP National Championships",
    664: "2026 Texas State SASP Championship Match",
    671: "2026 SASP National Championships",
}


class BatchRefreshError(RuntimeError):
    """Raised when batch selection or output setup cannot proceed."""


@dataclass(frozen=True)
class BatchRunResult:
    plan_path: Path
    results_path: Path
    errors_path: Path
    selected_count: int
    processed_count: int
    skipped_count: int
    failed_count: int
    dry_run: bool


def run_backfill(
    *,
    output_root: Path | str,
    profile: TeamProfile,
    match_ids: tuple[int, ...],
    from_date: date | None,
    to_date: date | None,
    post_types: tuple[str, ...],
    build_level: str,
    include_schedule: bool,
    max_matches: int,
    dry_run: bool,
    overwrite: bool,
    skip_unchanged: bool,
    allow_over_max: bool,
    client: SaspClient | None = None,
) -> BatchRunResult:
    """Plan or execute a bounded historical backfill."""
    root = Path(output_root)
    sasp_client = client or SaspClient()
    overrides = load_match_overrides("config/match_overrides.csv")
    catalog = _load_catalog(
        root,
        sasp_client,
        required=not bool(match_ids),
    )
    selected = _select_backfill_matches(
        catalog,
        overrides,
        match_ids,
        from_date,
        to_date,
        post_types,
    )
    selected = _guard_selection(selected, max_matches, allow_over_max)
    batch_dir = root / "backfill"
    plan_rows = [
        {
            "match_id": row["match_id"],
            "match_name": row["match_name"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "post_raw": row["post_raw"],
            "selected_reason": row["selected_reason"],
            "planned_build_level": build_level,
            "dry_run": str(dry_run).lower(),
            "notes": row.get("notes", ""),
        }
        for row in selected
    ]
    plan_path = batch_dir / "backfill_plan.csv"
    results_path = batch_dir / "backfill_results.csv"
    errors_path = batch_dir / "backfill_errors.csv"
    _write_csv(plan_path, BACKFILL_PLAN_COLUMNS, plan_rows)
    if dry_run:
        _write_csv(results_path, BACKFILL_RESULT_COLUMNS, [])
        _write_csv(errors_path, BACKFILL_ERROR_COLUMNS, [])
        return BatchRunResult(
            plan_path=plan_path,
            results_path=results_path,
            errors_path=errors_path,
            selected_count=len(selected),
            processed_count=0,
            skipped_count=0,
            failed_count=0,
            dry_run=True,
        )

    results, errors = _process_matches(
        selected,
        root,
        profile,
        build_level,
        include_schedule,
        overwrite,
        skip_unchanged,
        sasp_client,
        incremental=False,
    )
    _write_csv(results_path, BACKFILL_RESULT_COLUMNS, results)
    _write_csv(errors_path, BACKFILL_ERROR_COLUMNS, errors)
    return BatchRunResult(
        plan_path=plan_path,
        results_path=results_path,
        errors_path=errors_path,
        selected_count=len(selected),
        processed_count=sum(
            row["status"] == "SUCCESS" for row in results
        ),
        skipped_count=sum(
            row["status"] == "SKIPPED_UNCHANGED" for row in results
        ),
        failed_count=len(errors),
        dry_run=False,
    )


def run_incremental_refresh(
    *,
    output_root: Path | str,
    profile: TeamProfile,
    lookback_days: int,
    include_watched: bool,
    include_recent: bool,
    include_active: bool,
    include_schedule: bool,
    max_matches: int,
    dry_run: bool,
    build_level: str,
    skip_unchanged: bool,
    overwrite: bool,
    allow_over_max: bool,
    client: SaspClient | None = None,
) -> BatchRunResult:
    """Plan or execute watched, active, and recent match refreshes."""
    root = Path(output_root)
    sasp_client = client or SaspClient()
    overrides = load_match_overrides("config/match_overrides.csv")
    catalog = _load_catalog(root, sasp_client, required=True)
    watched = _load_watched_matches("config/watched_matches.csv")
    selected = _select_incremental_matches(
        catalog,
        overrides,
        watched,
        lookback_days,
        include_watched,
        include_recent,
        include_active,
    )
    selected = _guard_selection(selected, max_matches, allow_over_max)
    batch_dir = root / "incremental"
    candidate_rows = [
        {
            "match_id": row["match_id"],
            "match_name": row["match_name"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "post_raw": row["post_raw"],
            "candidate_reason": row["selected_reason"],
            "watched": str(row["watched"]).lower(),
            "active": str(row["active"]).lower(),
            "recent": str(row["recent"]).lower(),
            "planned_build_level": build_level,
            "dry_run": str(dry_run).lower(),
            "notes": row.get("notes", ""),
        }
        for row in selected
    ]
    candidates_path = batch_dir / "incremental_candidates.csv"
    results_path = batch_dir / "incremental_results.csv"
    errors_path = batch_dir / "incremental_errors.csv"
    _write_csv(
        candidates_path,
        INCREMENTAL_CANDIDATE_COLUMNS,
        candidate_rows,
    )
    if dry_run:
        _write_csv(results_path, INCREMENTAL_RESULT_COLUMNS, [])
        _write_csv(errors_path, BACKFILL_ERROR_COLUMNS, [])
        return BatchRunResult(
            plan_path=candidates_path,
            results_path=results_path,
            errors_path=errors_path,
            selected_count=len(selected),
            processed_count=0,
            skipped_count=0,
            failed_count=0,
            dry_run=True,
        )

    results, errors = _process_matches(
        selected,
        root,
        profile,
        build_level,
        include_schedule,
        overwrite,
        skip_unchanged,
        sasp_client,
        incremental=True,
    )
    _write_csv(results_path, INCREMENTAL_RESULT_COLUMNS, results)
    _write_csv(errors_path, BACKFILL_ERROR_COLUMNS, errors)
    return BatchRunResult(
        plan_path=candidates_path,
        results_path=results_path,
        errors_path=errors_path,
        selected_count=len(selected),
        processed_count=sum(
            row["status"] == "SUCCESS" for row in results
        ),
        skipped_count=sum(
            row["status"] == "SKIPPED_UNCHANGED" for row in results
        ),
        failed_count=len(errors),
        dry_run=False,
    )


def _process_matches(
    selected: list[dict[str, Any]],
    output_root: Path,
    profile: TeamProfile,
    build_level: str,
    include_schedule: bool,
    overwrite: bool,
    skip_unchanged: bool,
    client: SaspClient,
    *,
    incremental: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    manifest_path = output_root / "state" / "match_refresh_manifest.csv"
    manifest = load_manifest(manifest_path)
    for selected_match in selected:
        match_id = int(selected_match["match_id"])
        match_name = selected_match["match_name"]
        started = time.monotonic()
        output_dir = output_root / str(match_id)
        previous = manifest.get((str(match_id), profile.team_key), {})
        previous_hash = _manifest_raw_hash(previous)
        now = utc_now()
        try:
            client.fetch_match_snapshots(
                match_id=match_id,
                output_dir=output_dir,
                overwrite=overwrite,
                include_schedule=include_schedule,
            )
            hashes = raw_hashes(output_dir, match_id)
            current_hash = combined_raw_hash(hashes)
            changed = not previous_hash or current_hash != previous_hash
            if (
                skip_unchanged
                and previous_hash
                and not changed
                and build_level != "raw"
            ):
                data_status = previous.get("last_data_status", "")
                counts = _manifest_validation_counts(previous)
                status = "SKIPPED_UNCHANGED"
                notes = "Raw hashes match the previous successful check."
                update_manifest(
                    manifest_path,
                    {
                        "match_id": match_id,
                        "team_key": profile.team_key,
                        "match_name": match_name,
                        "last_checked_at": now,
                        "last_status": status,
                        **hashes,
                        "notes": notes,
                    },
                )
                result = _result_row(
                    selected_match,
                    build_level,
                    status,
                    data_status,
                    changed,
                    previous_hash,
                    current_hash,
                    0,
                    counts,
                    output_dir,
                    time.monotonic() - started,
                    notes,
                    incremental,
                )
                results.append(result)
                continue

            outcome = _run_build_level(
                match_id,
                output_dir,
                profile,
                build_level,
                include_schedule,
                overwrite,
                client,
            )
            counts = outcome["validation_counts"]
            data_status = outcome["data_status"]
            latest_snapshot = outcome.get("latest_snapshot_path", "")
            artifact_name = outcome.get("artifact_name", "")
            team_hash = directory_hash(
                output_dir
                / "team_report_tables"
                / profile.team_key
            )
            update_values = {
                "match_id": match_id,
                "team_key": profile.team_key,
                "match_name": match_name or outcome["match_name"],
                "last_checked_at": now,
                "last_success_at": now,
                "last_status": "SUCCESS",
                "last_data_status": data_status,
                **hashes,
                "team_report_hash": team_hash,
                "latest_snapshot_path": latest_snapshot,
                "latest_artifact_name": artifact_name,
                "validation_error_count": counts["ERROR"],
                "validation_warning_count": counts["WARNING"],
                "validation_review_count": counts["REVIEW"],
                "notes": outcome["notes"],
            }
            if changed:
                update_values["last_changed_at"] = now
            update_manifest(manifest_path, update_values)
            results.append(
                _result_row(
                    selected_match,
                    build_level,
                    "SUCCESS",
                    data_status,
                    changed,
                    previous_hash,
                    current_hash,
                    outcome["parsed_rows"],
                    counts,
                    output_dir,
                    time.monotonic() - started,
                    outcome["notes"],
                    incremental,
                )
            )
        except (
            SaspApiError,
            MatchParseError,
            MatchValidationError,
            MatchReportError,
            TeamReportError,
            MatchWorkbookError,
            TeamWorkbookError,
            NationalsOpsError,
            NationalsWorkbookError,
            RefreshManifestError,
            OSError,
            ValueError,
        ) as exc:
            error = {
                "match_id": match_id,
                "match_name": match_name,
                "step": build_level,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "notes": "Processing continued with the next match.",
            }
            errors.append(error)
            update_manifest(
                manifest_path,
                {
                    "match_id": match_id,
                    "team_key": profile.team_key,
                    "match_name": match_name,
                    "last_checked_at": now,
                    "last_status": "FAILED",
                    "notes": f"{type(exc).__name__}: {exc}",
                },
            )
    return results, errors


def _run_build_level(
    match_id: int,
    output_dir: Path,
    profile: TeamProfile,
    build_level: str,
    include_schedule: bool,
    overwrite: bool,
    client: SaspClient,
) -> dict[str, Any]:
    if build_level == "nationals":
        result = build_nationals_match(
            match_id=match_id,
            output_dir=output_dir,
            profile=profile,
            snapshot_label="batch",
            overwrite=False,
            include_schedule=include_schedule,
            client=client,
        )
        full = result.team_build.full_build
        return {
            "parsed_rows": _parse_row_count(full.parse_result),
            "validation_counts": _severity_counts(
                full.validation_result.severity_counts
            ),
            "data_status": result.operations_result.data_status,
            "match_name": _match_name(output_dir, match_id),
            "latest_snapshot_path": str(
                result.operations_result.snapshot_path
            ),
            "artifact_name": (
                f"nationals-{match_id}-{profile.team_key}-ops"
            ),
            "notes": "Nationals operations snapshot and workbook built.",
        }

    parsed_rows = 0
    counts = {"ERROR": 0, "WARNING": 0, "REVIEW": 0}
    notes = "Raw snapshots refreshed."
    if build_level in {"parse", "validate", "report", "team"}:
        parse_result = parse_match(match_id=match_id, output_dir=output_dir)
        parsed_rows = _parse_row_count(parse_result)
        notes = "Raw snapshots parsed."
    if build_level in {"validate", "report", "team"}:
        validation = validate_match(
            match_id=match_id,
            output_dir=output_dir,
        )
        counts = _severity_counts(validation.severity_counts)
        notes = "Parsed tables validated."
    if build_level in {"report", "team"}:
        build_match_report(match_id=match_id, output_dir=output_dir)
        notes = "Full report tables built."
    if build_level == "team":
        build_team_report(
            match_id=match_id,
            output_dir=output_dir,
            profile=profile,
        )
        notes = "Team report tables built; workbooks were not generated."
    return {
        "parsed_rows": parsed_rows,
        "validation_counts": counts,
        "data_status": _data_status(output_dir, profile),
        "match_name": _match_name(output_dir, match_id),
        "latest_snapshot_path": "",
        "artifact_name": "",
        "notes": notes,
    }


def _select_backfill_matches(
    catalog: dict[int, dict[str, str]],
    overrides: dict[int, MatchOverride],
    match_ids: tuple[int, ...],
    from_date: date | None,
    to_date: date | None,
    post_types: tuple[str, ...],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    if match_ids:
        for match_id in match_ids:
            override = overrides.get(match_id)
            if override and override.force_exclude:
                continue
            row = _catalog_row(catalog, match_id)
            row["selected_reason"] = "explicit_match_id"
            if override and override.force_include:
                row["selected_reason"] += ";force_include"
            selected.append(row)
        return selected

    for match_id, source in catalog.items():
        override = overrides.get(match_id)
        if override and override.force_exclude:
            continue
        start = _parse_date(source.get("start_date", ""))
        end = _parse_date(source.get("end_date", ""))
        if from_date and (end or start) and (end or start) < from_date:
            continue
        if to_date and (start or end) and (start or end) > to_date:
            continue
        if post_types and (
            source.get("post_raw", "").strip().upper() not in post_types
        ):
            continue
        row = _catalog_row(catalog, match_id)
        row["selected_reason"] = "catalog_filters"
        if override and override.force_include:
            row["selected_reason"] += ";force_include"
        selected.append(row)
    return sorted(selected, key=_date_sort_key)


def _select_incremental_matches(
    catalog: dict[int, dict[str, str]],
    overrides: dict[int, MatchOverride],
    watched: dict[int, dict[str, str]],
    lookback_days: int,
    include_watched: bool,
    include_recent: bool,
    include_active: bool,
) -> list[dict[str, Any]]:
    today = date.today()
    recent_cutoff = today - timedelta(days=lookback_days)
    match_ids = set(catalog)
    if include_watched:
        match_ids.update(
            match_id
            for match_id, row in watched.items()
            if _truthy(row.get("active"))
        )
    selected: list[dict[str, Any]] = []
    for match_id in match_ids:
        override = overrides.get(match_id)
        if override and override.force_exclude:
            continue
        source = catalog.get(match_id, {})
        watch_row = watched.get(match_id, {})
        is_watched = (
            include_watched and _truthy(watch_row.get("active"))
        )
        start = _parse_date(source.get("start_date", ""))
        end = _parse_date(source.get("end_date", ""))
        is_active = bool(
            include_active
            and start
            and end
            and start <= today <= end
        )
        is_recent = bool(
            include_recent
            and end
            and recent_cutoff <= end <= today
        )
        force_include = bool(override and override.force_include)
        reasons = [
            reason
            for enabled, reason in (
                (is_watched, "watched_active"),
                (is_active, "currently_active"),
                (is_recent, f"ended_within_{lookback_days}_days"),
                (force_include, "force_include"),
            )
            if enabled
        ]
        if not reasons:
            continue
        row = _catalog_row(catalog, match_id)
        if watch_row.get("label") and not row["match_name"]:
            row["match_name"] = watch_row["label"]
        row.update(
            {
                "selected_reason": ";".join(reasons),
                "watched": is_watched,
                "active": is_active,
                "recent": is_recent,
                "notes": watch_row.get("notes", ""),
            }
        )
        selected.append(row)
    return sorted(selected, key=_incremental_sort_key)


def _load_catalog(
    output_root: Path,
    client: SaspClient,
    *,
    required: bool,
) -> dict[int, dict[str, str]]:
    path = (
        output_root
        / "discovery"
        / "tables"
        / "effective_match_index.csv"
    )
    if not path.exists() and required:
        discover_matches(
            client,
            output_dir=output_root / "discovery",
            overrides_path="config/match_overrides.csv",
            overwrite=False,
        )
    if not path.exists():
        return {}
    rows = _read_csv(path)
    return {
        int(row["match_id"]): row
        for row in rows
        if row.get("match_id", "").isdigit()
    }


def _load_watched_matches(
    path: Path | str,
) -> dict[int, dict[str, str]]:
    return {
        int(row["match_id"]): row
        for row in _read_csv(Path(path))
        if row.get("match_id", "").isdigit()
    }


def _catalog_row(
    catalog: dict[int, dict[str, str]],
    match_id: int,
) -> dict[str, Any]:
    source = catalog.get(match_id, {})
    return {
        "match_id": match_id,
        "match_name": (
            source.get("name")
            or KNOWN_MATCHES.get(match_id, f"Match {match_id}")
        ),
        "start_date": source.get("start_date", ""),
        "end_date": source.get("end_date", ""),
        "post_raw": source.get("post_raw", ""),
        "notes": source.get("override_notes", ""),
        "watched": False,
        "active": False,
        "recent": False,
    }


def _guard_selection(
    selected: list[dict[str, Any]],
    max_matches: int,
    allow_over_max: bool,
) -> list[dict[str, Any]]:
    if max_matches < 1:
        raise BatchRefreshError("max_matches must be at least 1.")
    if len(selected) > max_matches and not allow_over_max:
        original_count = len(selected)
        selected = selected[:max_matches]
        for row in selected:
            row["notes"] = " ".join(
                item
                for item in (
                    row.get("notes", ""),
                    (
                        f"Selection capped at {max_matches} of "
                        f"{original_count} candidates."
                    ),
                )
                if item
            )
    return selected


def _result_row(
    selected: dict[str, Any],
    build_level: str,
    status: str,
    data_status: str,
    changed: bool,
    previous_hash: str,
    current_hash: str,
    parsed_rows: int,
    counts: dict[str, int],
    output_dir: Path,
    elapsed: float,
    notes: str,
    incremental: bool,
) -> dict[str, Any]:
    if incremental:
        return {
            "match_id": selected["match_id"],
            "match_name": selected["match_name"],
            "status": status,
            "data_status": data_status,
            "changed": str(changed).lower(),
            "previous_hash": previous_hash,
            "current_hash": current_hash,
            "validation_error_count": counts["ERROR"],
            "validation_warning_count": counts["WARNING"],
            "validation_review_count": counts["REVIEW"],
            "output_path": str(output_dir),
            "notes": notes,
        }
    return {
        "match_id": selected["match_id"],
        "match_name": selected["match_name"],
        "build_level": build_level,
        "status": status,
        "data_status": data_status,
        "raw_changed": str(changed).lower(),
        "parsed_rows": parsed_rows,
        "validation_error_count": counts["ERROR"],
        "validation_warning_count": counts["WARNING"],
        "validation_review_count": counts["REVIEW"],
        "artifact_or_output_path": str(output_dir),
        "elapsed_seconds": round(elapsed, 3),
        "notes": notes,
    }


def _manifest_raw_hash(row: dict[str, str]) -> str:
    return combined_raw_hash(
        {
            "raw_slots_hash": row.get("raw_slots_hash", ""),
            "raw_leaderboard_hash": row.get(
                "raw_leaderboard_hash",
                "",
            ),
            "raw_schedule_hash": row.get("raw_schedule_hash", ""),
        }
    )


def _manifest_validation_counts(
    row: dict[str, str],
) -> dict[str, int]:
    return {
        "ERROR": _integer(row.get("validation_error_count")),
        "WARNING": _integer(row.get("validation_warning_count")),
        "REVIEW": _integer(row.get("validation_review_count")),
    }


def _severity_counts(values: dict[str, int]) -> dict[str, int]:
    return {
        severity: int(values.get(severity, 0))
        for severity in ("ERROR", "WARNING", "REVIEW")
    }


def _parse_row_count(result: Any) -> int:
    return sum(
        (
            result.match_score_rows,
            result.ranking_rows,
            result.squad_result_rows,
            result.stage_score_rows,
        )
    )


def _data_status(output_dir: Path, profile: TeamProfile) -> str:
    path = output_dir / "tables" / "match_scores.csv"
    if not path.exists():
        return "raw_only"
    rows = [
        row
        for row in _read_csv(path)
        if profile.matches_name(row.get("team_name"))
    ]
    if not rows:
        return "no_team_entries"
    scored = sum(bool(row.get("match_score_seconds")) for row in rows)
    if scored == 0:
        return "no_scores"
    if scored < len(rows):
        return "partial"
    return "complete"


def _match_name(output_dir: Path, match_id: int) -> str:
    path = output_dir / "tables" / "match_scores.csv"
    if path.exists():
        for row in _read_csv(path):
            if row.get("match_name"):
                return row["match_name"]
    return KNOWN_MATCHES.get(match_id, f"Match {match_id}")


def _date_sort_key(row: dict[str, Any]) -> tuple[str, int]:
    return (row.get("start_date") or "9999-12-31", row["match_id"])


def _incremental_sort_key(
    row: dict[str, Any],
) -> tuple[int, str, int]:
    priority = (
        0
        if row.get("watched")
        else 1
        if row.get("active")
        else 2
        if "force_include" in row.get("selected_reason", "")
        else 3
    )
    return (
        priority,
        row.get("start_date") or "9999-12-31",
        row["match_id"],
    )


def _parse_date(value: str) -> date | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    for candidate in (cleaned, cleaned[:10]):
        try:
            return datetime.fromisoformat(
                candidate.replace("Z", "+00:00")
            ).date()
        except ValueError:
            continue
    return None


def _truthy(value: Any) -> bool:
    return str(value).strip().casefold() == "true"


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            return list(csv.DictReader(source))
    except (OSError, csv.Error) as exc:
        raise BatchRefreshError(f"Could not read {path}: {exc}") from exc


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
        raise BatchRefreshError(f"Could not write {path}: {exc}") from exc
