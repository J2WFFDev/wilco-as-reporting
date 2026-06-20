"""Team profile configuration for team-focused reporting."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


class TeamProfileError(RuntimeError):
    """Raised when a team profile cannot be loaded."""


@dataclass(frozen=True)
class TeamProfile:
    team_key: str
    team_name: str
    team_number: str
    aliases: tuple[str, ...]
    active: bool
    notes: str

    def matches_name(self, value: str | None) -> bool:
        normalized = (value or "").strip().casefold()
        return normalized in {
            name.casefold()
            for name in (self.team_name, *self.aliases)
        }


def load_team_profile(
    team_key: str,
    path: Path | str = Path("config/team_profiles.csv"),
) -> TeamProfile:
    """Load one active team profile by key."""
    profile_path = Path(path)
    try:
        with profile_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as source:
            rows = list(csv.DictReader(source))
    except FileNotFoundError as exc:
        raise TeamProfileError(
            f"Missing team profile file: {profile_path}"
        ) from exc
    except (OSError, csv.Error) as exc:
        raise TeamProfileError(
            f"Could not read team profiles {profile_path}: {exc}"
        ) from exc

    matches = [
        row
        for row in rows
        if row.get("team_key", "").strip().casefold()
        == team_key.strip().casefold()
    ]
    if not matches:
        raise TeamProfileError(f"Unknown team key: {team_key}")
    if len(matches) > 1:
        raise TeamProfileError(f"Duplicate team key: {team_key}")

    row = matches[0]
    active = row.get("active", "").strip().casefold() == "true"
    if not active:
        raise TeamProfileError(f"Team profile is inactive: {team_key}")
    aliases = tuple(
        alias.strip()
        for alias in row.get("aliases", "").split("|")
        if alias.strip()
    )
    return TeamProfile(
        team_key=row.get("team_key", "").strip(),
        team_name=row.get("team_name", "").strip(),
        team_number=row.get("team_number", "").strip(),
        aliases=aliases,
        active=active,
        notes=row.get("notes", "").strip(),
    )
