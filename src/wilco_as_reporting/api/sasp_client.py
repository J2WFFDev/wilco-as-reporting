"""Fetch and preserve raw JSON snapshots from the SASP API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


class SaspApiError(RuntimeError):
    """Base error for SASP API and snapshot failures."""


class SaspHttpError(SaspApiError):
    """Raised when an SASP endpoint returns an HTTP or network failure."""


class SaspInvalidJsonError(SaspApiError):
    """Raised when an SASP endpoint does not return valid JSON."""


class SnapshotWriteError(SaspApiError):
    """Raised when a raw snapshot directory or file cannot be written."""


@dataclass(frozen=True)
class SnapshotResult:
    path: Path
    status: str


@dataclass(frozen=True)
class MatchSnapshots:
    slots: SnapshotResult
    leaderboard: SnapshotResult
    schedule: SnapshotResult | None = None


class SaspClient:
    """Client for the public SASP match endpoints."""

    BASE_URL = "https://virtual.sssfonline.com/api/shot"

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout

    def fetch_slots(self, match_id: int) -> Any:
        url = f"{self.BASE_URL}/SASP/competitions/{match_id}/slots"
        return self._get_json(url)

    def fetch_leaderboard(self, match_id: int) -> Any:
        url = f"{self.BASE_URL}/sasp-leaderboard/{match_id}"
        return self._get_json(url)

    def fetch_schedule(self, match_id: int) -> Any:
        url = f"{self.BASE_URL}/sasp-schedule/{match_id}"
        return self._get_json(url)

    def fetch_competitions_page(self, page: int) -> Any:
        url = f"{self.BASE_URL}/SASP/competitions"
        return self._get_json(url, params={"type": "S", "page": page})

    def fetch_match_snapshots(
        self,
        match_id: int,
        output_dir: Path | str,
        overwrite: bool = False,
        include_schedule: bool = False,
    ) -> MatchSnapshots:
        output_path = Path(output_dir)
        raw_dir = output_path / "raw"
        slots_path = raw_dir / f"{match_id}_slots.json"
        leaderboard_path = raw_dir / f"{match_id}_leaderboard.json"
        schedule_path = raw_dir / f"{match_id}_schedule.json"

        self._ensure_raw_directory(raw_dir)

        slots_exists = slots_path.exists()
        leaderboard_exists = leaderboard_path.exists()

        slots_data = None
        leaderboard_data = None
        if overwrite or not slots_exists:
            slots_data = self.fetch_slots(match_id)
        if overwrite or not leaderboard_exists:
            leaderboard_data = self.fetch_leaderboard(match_id)

        slots_result = self._save_snapshot(
            slots_path,
            slots_data,
            exists=slots_exists,
            overwrite=overwrite,
        )
        leaderboard_result = self._save_snapshot(
            leaderboard_path,
            leaderboard_data,
            exists=leaderboard_exists,
            overwrite=overwrite,
        )
        schedule_result = None
        if include_schedule:
            schedule_exists = schedule_path.exists()
            schedule_data = None
            if overwrite or not schedule_exists:
                schedule_data = self.fetch_schedule(match_id)
            schedule_result = self._save_snapshot(
                schedule_path,
                schedule_data,
                exists=schedule_exists,
                overwrite=overwrite,
            )

        return MatchSnapshots(
            slots=slots_result,
            leaderboard=leaderboard_result,
            schedule=schedule_result,
        )

    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SaspHttpError(f"HTTP request failed for {url}: {exc}") from exc

        try:
            return response.json()
        except requests.JSONDecodeError as exc:
            raise SaspInvalidJsonError(
                f"Invalid JSON returned by {url}: {exc}"
            ) from exc

    @staticmethod
    def _ensure_raw_directory(raw_dir: Path) -> None:
        try:
            raw_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise SnapshotWriteError(
                f"Could not create output directory {raw_dir}: {exc}"
            ) from exc

        if not raw_dir.is_dir():
            raise SnapshotWriteError(
                f"Output path is not a directory: {raw_dir}"
            )

    @staticmethod
    def _save_snapshot(
        path: Path,
        data: Any,
        *,
        exists: bool,
        overwrite: bool,
    ) -> SnapshotResult:
        if exists and not overwrite:
            return SnapshotResult(path=path, status="already existed")

        try:
            with path.open("w", encoding="utf-8") as snapshot_file:
                json.dump(data, snapshot_file, indent=2, ensure_ascii=False)
                snapshot_file.write("\n")
        except (OSError, TypeError, ValueError) as exc:
            raise SnapshotWriteError(
                f"Could not write raw snapshot {path}: {exc}"
            ) from exc

        return SnapshotResult(path=path, status="written")
