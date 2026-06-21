"""Classify whether a raw SASP JSON file contains useful endpoint data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JsonContentStatus:
    file_exists: bool
    file_size_bytes: int
    json_valid: bool
    json_kind: str
    json_empty: bool
    useful_content: bool
    issue_type: str
    content_issue: str


def inspect_json_file(path: Path | str) -> JsonContentStatus:
    """Read and classify one local JSON file without modifying it."""
    file_path = Path(path)
    try:
        size = file_path.stat().st_size
    except FileNotFoundError:
        return JsonContentStatus(
            file_exists=False,
            file_size_bytes=0,
            json_valid=False,
            json_kind="missing",
            json_empty=True,
            useful_content=False,
            issue_type="missing_file",
            content_issue="Expected raw JSON file is missing.",
        )
    except OSError as exc:
        return JsonContentStatus(
            file_exists=file_path.exists(),
            file_size_bytes=0,
            json_valid=False,
            json_kind="invalid",
            json_empty=True,
            useful_content=False,
            issue_type="invalid_json",
            content_issue=f"Could not inspect JSON file: {exc}",
        )
    if not file_path.is_file():
        return JsonContentStatus(
            file_exists=True,
            file_size_bytes=0,
            json_valid=False,
            json_kind="invalid",
            json_empty=True,
            useful_content=False,
            issue_type="invalid_json",
            content_issue="Expected path is not a regular file.",
        )
    if size == 0:
        return JsonContentStatus(
            file_exists=True,
            file_size_bytes=0,
            json_valid=False,
            json_kind="invalid",
            json_empty=True,
            useful_content=False,
            issue_type="zero_byte_file",
            content_issue="JSON file is zero bytes.",
        )
    try:
        with file_path.open("r", encoding="utf-8-sig") as source:
            value = json.load(source)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return JsonContentStatus(
            file_exists=True,
            file_size_bytes=size,
            json_valid=False,
            json_kind="invalid",
            json_empty=True,
            useful_content=False,
            issue_type="invalid_json",
            content_issue=f"File does not contain valid JSON: {exc}",
        )
    return classify_json_value(value, file_exists=True, file_size_bytes=size)


def classify_json_value(
    value: Any,
    *,
    file_exists: bool = True,
    file_size_bytes: int = 0,
) -> JsonContentStatus:
    """Classify an already parsed endpoint response."""
    if value is None:
        return _status(
            file_exists,
            file_size_bytes,
            "null",
            True,
            False,
            "json_null",
            "Endpoint returned JSON null.",
        )
    if isinstance(value, list):
        if value:
            return _status(
                file_exists,
                file_size_bytes,
                "list",
                False,
                True,
                "",
                "",
            )
        return _status(
            file_exists,
            file_size_bytes,
            "list",
            True,
            False,
            "empty_list",
            "Endpoint returned an empty JSON list.",
        )
    if isinstance(value, dict):
        if value:
            return _status(
                file_exists,
                file_size_bytes,
                "object",
                False,
                True,
                "",
                "",
            )
        return _status(
            file_exists,
            file_size_bytes,
            "object",
            True,
            False,
            "empty_object",
            "Endpoint returned an empty JSON object.",
        )
    if isinstance(value, bool):
        kind = "boolean"
    elif isinstance(value, str):
        kind = "string"
    elif isinstance(value, (int, float)):
        kind = "number"
    else:
        kind = "invalid"
    return _status(
        file_exists,
        file_size_bytes,
        kind,
        False,
        False,
        "primitive_json",
        f"Endpoint returned primitive JSON ({kind}), not match data.",
    )


def _status(
    file_exists: bool,
    file_size_bytes: int,
    kind: str,
    empty: bool,
    useful: bool,
    issue_type: str,
    issue: str,
) -> JsonContentStatus:
    return JsonContentStatus(
        file_exists=file_exists,
        file_size_bytes=file_size_bytes,
        json_valid=True,
        json_kind=kind,
        json_empty=empty,
        useful_content=useful,
        issue_type=issue_type,
        content_issue=issue,
    )
