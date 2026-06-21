"""Desktop-friendly, rate-limited raw SASP JSON downloader."""

from __future__ import annotations

import csv
import json
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import requests

from wilco_as_reporting.api.sasp_client import SaspClient
from wilco_as_reporting.raw_content import (
    classify_json_value,
    inspect_json_file,
)

DOWNLOAD_PLAN_COLUMNS = (
    "match_id",
    "endpoint_type",
    "output_path",
    "exists_already",
    "planned_action",
    "notes",
)

DOWNLOAD_RESULT_COLUMNS = (
    "match_id",
    "endpoint_type",
    "status",
    "output_path",
    "downloaded",
    "skipped_existing",
    "http_status",
    "retry_count",
    "elapsed_seconds",
    "notes",
)

DOWNLOAD_ERROR_COLUMNS = (
    "match_id",
    "endpoint_type",
    "error_type",
    "error_message",
    "retry_count",
    "notes",
)

ENDPOINTS = {
    "slots": "/SASP/competitions/{match_id}/slots",
    "leaderboard": "/sasp-leaderboard/{match_id}",
    "schedule": "/sasp-schedule/{match_id}",
}


class RawDownloadError(RuntimeError):
    """Raised when downloader configuration or output setup is invalid."""


@dataclass(frozen=True)
class RawDownloadResult:
    plan_path: Path
    results_path: Path
    errors_path: Path
    planned_count: int
    valid_download_count: int
    no_content_download_count: int
    skipped_valid_count: int
    skipped_no_content_count: int
    failed_count: int
    dry_run: bool


class RequestWindowLimiter:
    """Conservative sliding-window request limiter."""

    def __init__(
        self,
        requests_per_window: int,
        window_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if requests_per_window < 1:
            raise RawDownloadError(
                "requests_per_window must be at least 1."
            )
        if window_seconds <= 0:
            raise RawDownloadError("window_seconds must be positive.")
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.clock = clock
        self.sleep = sleep
        self.request_times: deque[float] = deque()

    def wait(self) -> float:
        """Wait until one request is allowed and reserve its slot."""
        now = self.clock()
        self._discard_expired(now)
        waited = 0.0
        if len(self.request_times) >= self.requests_per_window:
            wait_seconds = (
                self.window_seconds
                - (now - self.request_times[0])
                + 0.05
            )
            if wait_seconds > 0:
                self.sleep(wait_seconds)
                waited = wait_seconds
            now = self.clock()
            self._discard_expired(now)
        self.request_times.append(now)
        return waited

    def _discard_expired(self, now: float) -> None:
        while (
            self.request_times
            and now - self.request_times[0] >= self.window_seconds
        ):
            self.request_times.popleft()


def download_raw_matches(
    *,
    match_ids: tuple[int, ...],
    output_root: Path | str = Path("output"),
    include_schedule: bool = False,
    skip_existing: bool = True,
    overwrite: bool = False,
    requests_per_window: int = 4,
    window_seconds: float = 30.0,
    retry_count: int = 3,
    retry_backoff_seconds: float = 30.0,
    dry_run: bool = False,
    max_matches: int = 25,
    session: requests.Session | None = None,
    progress: Callable[[str], None] = print,
) -> RawDownloadResult:
    """Plan or download raw JSON for a bounded set of matches."""
    match_ids = tuple(dict.fromkeys(match_ids))
    if not match_ids:
        raise RawDownloadError("At least one match ID is required.")
    if len(match_ids) > max_matches:
        raise RawDownloadError(
            f"{len(match_ids)} match IDs exceed --max-matches "
            f"{max_matches}."
        )
    if max_matches < 1:
        raise RawDownloadError("max_matches must be at least 1.")
    if retry_count < 0:
        raise RawDownloadError("retry_count cannot be negative.")
    if retry_backoff_seconds < 0:
        raise RawDownloadError(
            "retry_backoff_seconds cannot be negative."
        )
    if overwrite:
        skip_existing = False

    output_path = Path(output_root)
    downloads_dir = output_path / "downloads"
    endpoints = ["slots", "leaderboard"]
    if include_schedule:
        endpoints.append("schedule")
    plan_rows = _build_plan(
        match_ids,
        output_path,
        endpoints,
        skip_existing,
        overwrite,
    )
    plan_path = downloads_dir / "download_plan.csv"
    results_path = downloads_dir / "download_results.csv"
    errors_path = downloads_dir / "download_errors.csv"
    _write_csv(plan_path, DOWNLOAD_PLAN_COLUMNS, plan_rows)

    if dry_run:
        _write_csv(results_path, DOWNLOAD_RESULT_COLUMNS, [])
        _write_csv(errors_path, DOWNLOAD_ERROR_COLUMNS, [])
        progress(
            f"Dry run planned {len(plan_rows)} endpoint download(s)."
        )
        return RawDownloadResult(
            plan_path=plan_path,
            results_path=results_path,
            errors_path=errors_path,
            planned_count=len(plan_rows),
            valid_download_count=0,
            no_content_download_count=0,
            skipped_valid_count=0,
            skipped_no_content_count=0,
            failed_count=0,
            dry_run=True,
        )

    limiter = RequestWindowLimiter(
        requests_per_window,
        window_seconds,
    )
    http = session or requests.Session()
    result_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []
    total = len(plan_rows)
    for number, plan in enumerate(plan_rows, start=1):
        match_id = int(plan["match_id"])
        endpoint_type = str(plan["endpoint_type"])
        destination = Path(str(plan["output_path"]))
        prefix = f"[{number}/{total}] Match {match_id} {endpoint_type}"
        if plan["planned_action"] == "skip_existing":
            content = inspect_json_file(destination)
            status = (
                "SKIPPED_EXISTING_VALID"
                if content.useful_content
                else "SKIPPED_EXISTING_NO_CONTENT"
            )
            progress(
                f"{prefix}: "
                + (
                    "skipped existing useful JSON"
                    if content.useful_content
                    else (
                        "skipped existing file with no useful content "
                        f"({content.issue_type})"
                    )
                )
            )
            result_rows.append(
                _result_row(
                    plan,
                    status=status,
                    downloaded=False,
                    skipped_existing=True,
                    http_status="",
                    retries=0,
                    elapsed=0.0,
                    notes=(
                        "Existing useful JSON preserved."
                        if content.useful_content
                        else content.content_issue
                    ),
                )
            )
            continue

        progress(f"{prefix}: downloading")
        result, error = _download_one(
            http,
            limiter,
            match_id,
            endpoint_type,
            destination,
            retry_count,
            retry_backoff_seconds,
            progress,
        )
        if result:
            result_rows.append(result)
            progress(
                f"{prefix}: downloaded "
                f"({result['elapsed_seconds']} seconds)"
            )
        if error:
            error_rows.append(error)
            result_rows.append(
                _result_row(
                    plan,
                    status="FAILED",
                    downloaded=False,
                    skipped_existing=False,
                    http_status=error.get("http_status", ""),
                    retries=int(error["retry_count"]),
                    elapsed=round(
                        time.monotonic()
                        - float(error["started_at"]),
                        3,
                    ),
                    notes=str(error["error_message"]),
                )
            )
            progress(
                f"{prefix}: failed after "
                f"{error['retry_count']} retry attempt(s)"
            )

    _write_csv(results_path, DOWNLOAD_RESULT_COLUMNS, result_rows)
    _write_csv(errors_path, DOWNLOAD_ERROR_COLUMNS, error_rows)
    return RawDownloadResult(
        plan_path=plan_path,
        results_path=results_path,
        errors_path=errors_path,
        planned_count=len(plan_rows),
        valid_download_count=sum(
            row["status"] == "DOWNLOADED_VALID"
            for row in result_rows
        ),
        no_content_download_count=sum(
            row["status"] == "DOWNLOADED_NO_CONTENT"
            for row in result_rows
        ),
        skipped_valid_count=sum(
            row["status"] == "SKIPPED_EXISTING_VALID"
            for row in result_rows
        ),
        skipped_no_content_count=sum(
            row["status"] == "SKIPPED_EXISTING_NO_CONTENT"
            for row in result_rows
        ),
        failed_count=len(error_rows),
        dry_run=False,
    )


def _build_plan(
    match_ids: tuple[int, ...],
    output_root: Path,
    endpoints: list[str],
    skip_existing: bool,
    overwrite: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match_id in match_ids:
        for endpoint_type in endpoints:
            path = (
                output_root
                / str(match_id)
                / "raw"
                / f"{match_id}_{endpoint_type}.json"
            )
            exists = path.exists()
            if exists and skip_existing and not overwrite:
                action = "skip_existing"
                notes = "Existing file will be preserved."
            elif exists and overwrite:
                action = "overwrite"
                notes = "Existing file will be replaced."
            else:
                action = "download"
                notes = ""
            rows.append(
                {
                    "match_id": match_id,
                    "endpoint_type": endpoint_type,
                    "output_path": str(path),
                    "exists_already": str(exists).lower(),
                    "planned_action": action,
                    "notes": notes,
                }
            )
    return rows


def _download_one(
    session: requests.Session,
    limiter: RequestWindowLimiter,
    match_id: int,
    endpoint_type: str,
    destination: Path,
    retry_limit: int,
    retry_backoff_seconds: float,
    progress: Callable[[str], None],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    url = (
        SaspClient.BASE_URL
        + ENDPOINTS[endpoint_type].format(match_id=match_id)
    )
    started = time.monotonic()
    last_status: int | str = ""
    for attempt in range(retry_limit + 1):
        waited = limiter.wait()
        if waited:
            progress(
                f"Rate limit window full; waited {waited:.1f} seconds."
            )
        try:
            response = session.get(url, timeout=30.0)
            last_status = response.status_code
            if _rate_limited(response):
                if attempt >= retry_limit:
                    raise requests.HTTPError(
                        f"Rate limited with HTTP {response.status_code}",
                        response=response,
                    )
                wait_seconds = _retry_wait(
                    response,
                    retry_backoff_seconds,
                )
                progress(
                    f"Rate limit response for Match {match_id} "
                    f"{endpoint_type}; retrying in "
                    f"{wait_seconds:.1f} seconds."
                )
                time.sleep(wait_seconds)
                continue
            response.raise_for_status()
            try:
                payload = response.json()
            except requests.JSONDecodeError as exc:
                raise ValueError(
                    f"Endpoint returned invalid JSON: {exc}"
                ) from exc
            _write_json(destination, payload)
            content = classify_json_value(
                payload,
                file_exists=True,
                file_size_bytes=destination.stat().st_size,
            )
            status = (
                "DOWNLOADED_VALID"
                if content.useful_content
                else "DOWNLOADED_NO_CONTENT"
            )
            return (
                {
                    "match_id": match_id,
                    "endpoint_type": endpoint_type,
                    "status": status,
                    "output_path": str(destination),
                    "downloaded": "true",
                    "skipped_existing": "false",
                    "http_status": response.status_code,
                    "retry_count": attempt,
                    "elapsed_seconds": round(
                        time.monotonic() - started,
                        3,
                    ),
                    "notes": content.content_issue,
                },
                None,
            )
        except (requests.RequestException, OSError, ValueError) as exc:
            if (
                attempt < retry_limit
                and _retryable_exception(exc)
            ):
                wait_seconds = retry_backoff_seconds * (attempt + 1)
                progress(
                    f"Temporary error for Match {match_id} "
                    f"{endpoint_type}: {exc}. Retrying in "
                    f"{wait_seconds:.1f} seconds."
                )
                time.sleep(wait_seconds)
                continue
            return (
                None,
                {
                    "match_id": match_id,
                    "endpoint_type": endpoint_type,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "retry_count": attempt,
                    "http_status": last_status,
                    "started_at": started,
                    "notes": (
                        f"Last HTTP status: {last_status}."
                        if last_status != ""
                        else ""
                    ),
                },
            )
    raise AssertionError("Download retry loop exited unexpectedly.")


def _rate_limited(response: requests.Response) -> bool:
    if response.status_code == 429:
        return True
    if response.status_code not in {403, 503}:
        return False
    text = response.text.casefold()
    return "rate limit" in text or "too many request" in text


def _retry_wait(
    response: requests.Response,
    fallback: float,
) -> float:
    retry_after = response.headers.get("Retry-After", "").strip()
    try:
        return max(float(retry_after), fallback)
    except ValueError:
        return fallback


def _retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        return bool(
            response is not None
            and (
                _rate_limited(response)
                or response.status_code >= 500
            )
        )
    return False


def _result_row(
    plan: dict[str, Any],
    *,
    status: str,
    downloaded: bool,
    skipped_existing: bool,
    http_status: int | str,
    retries: int,
    elapsed: float,
    notes: str,
) -> dict[str, Any]:
    return {
        "match_id": plan["match_id"],
        "endpoint_type": plan["endpoint_type"],
        "status": status,
        "output_path": plan["output_path"],
        "downloaded": str(downloaded).lower(),
        "skipped_existing": str(skipped_existing).lower(),
        "http_status": http_status,
        "retry_count": retries,
        "elapsed_seconds": round(elapsed, 3),
        "notes": notes,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as target:
        json.dump(payload, target, indent=2, ensure_ascii=False)
        target.write("\n")


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
        raise RawDownloadError(f"Could not write {path}: {exc}") from exc
