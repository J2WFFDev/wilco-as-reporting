"""Shared athlete alias resolution for coach-facing local outputs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AthleteAliasError(RuntimeError):
    """Raised when the athlete alias configuration is invalid."""


@dataclass(frozen=True)
class AthleteAlias:
    canonical_name: str
    canonical_id: str
    alias_name: str
    alias_id: str
    notes: str


def load_athlete_aliases(
    path: Path | str = Path("config/athlete_aliases.csv"),
) -> tuple[AthleteAlias, ...]:
    """Load active athlete aliases without changing source data."""
    alias_path = Path(path)
    if not alias_path.exists():
        return ()
    try:
        with alias_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise AthleteAliasError(
            f"Could not read athlete aliases {alias_path}: {exc}"
        ) from exc
    aliases: list[AthleteAlias] = []
    for row_number, row in enumerate(rows, 2):
        if row.get("active", "").strip().casefold() not in {
            "true",
            "yes",
            "1",
        }:
            continue
        canonical_name = row.get("canonical_athlete_name", "").strip()
        alias_name = row.get("alias_athlete_name", "").strip()
        if not canonical_name or not alias_name:
            raise AthleteAliasError(
                f"Alias row {row_number} requires canonical and alias names."
            )
        canonical_id = row.get("canonical_athlete_id", "").strip()
        alias_id = row.get("alias_athlete_id", "").strip()
        if canonical_id and alias_id and canonical_id != alias_id:
            raise AthleteAliasError(
                f"Alias row {row_number} has conflicting athlete IDs."
            )
        aliases.append(
            AthleteAlias(
                canonical_name=canonical_name,
                canonical_id=canonical_id or alias_id,
                alias_name=alias_name,
                alias_id=alias_id,
                notes=row.get("notes", "").strip(),
            )
        )
    return tuple(aliases)


def apply_athlete_aliases(
    rows: list[dict[str, Any]],
    aliases: tuple[AthleteAlias, ...],
) -> list[dict[str, Any]]:
    """Return copied rows with canonical identity and audit fields."""
    by_id = {
        alias.alias_id: alias
        for alias in aliases
        if alias.alias_id
    }
    by_name = {
        alias.alias_name.casefold(): alias
        for alias in aliases
    }
    resolved: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        original_name = str(row.get("athlete_name", "")).strip()
        athlete_id = str(row.get("athlete_id", "")).strip()
        alias = by_id.get(athlete_id) or by_name.get(
            original_name.casefold()
        )
        row["original_athlete_name"] = original_name
        if alias:
            row["athlete_name"] = alias.canonical_name
            row["athlete_id"] = alias.canonical_id or athlete_id
            if original_name.casefold() != alias.canonical_name.casefold():
                row["identity_resolution_note"] = (
                    f"Canonicalized {original_name!r} to "
                    f"{alias.canonical_name!r}. {alias.notes}"
                ).strip()
            else:
                row["identity_resolution_note"] = (
                    "Canonical identity matched the alias configuration."
                )
        else:
            row["identity_resolution_note"] = "No alias mapping applied."
        resolved.append(row)
    return resolved
