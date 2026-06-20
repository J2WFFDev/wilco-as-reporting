"""Validate parsed SASP match score tables."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

TOLERANCE_SECONDS = 0.01

SUMMARY_COLUMNS = (
    "match_id",
    "check_name",
    "severity",
    "status",
    "finding_count",
    "notes",
)

FINDING_COLUMNS = (
    "match_id",
    "check_name",
    "severity",
    "finding_type",
    "entity_type",
    "entity_id",
    "athlete_name",
    "team_name",
    "discipline",
    "stage_number",
    "stage_name",
    "expected_value",
    "actual_value",
    "difference",
    "message",
)

MATCH_RECONCILIATION_COLUMNS = (
    "match_id",
    "entity_id",
    "athlete_id",
    "athlete_name",
    "team_name",
    "discipline_id",
    "discipline",
    "entry_occurrence",
    "stage_count",
    "scored_stage_count",
    "stage_total_seconds",
    "match_score_seconds",
    "difference",
    "reconciliation_status",
    "notes",
)

STAGE_RECONCILIATION_COLUMNS = (
    "match_id",
    "entity_id",
    "athlete_id",
    "athlete_name",
    "team_name",
    "discipline_id",
    "discipline",
    "entry_occurrence",
    "stage_number",
    "stage_name",
    "expected_counting_string_count",
    "observed_nonzero_string_count",
    "stage_score_seconds",
    "expected_scored_avg_seconds",
    "actual_scored_avg_seconds",
    "average_difference",
    "fastest_string_seconds",
    "penalty_count",
    "reconciliation_status",
    "notes",
)

SQUAD_RECONCILIATION_COLUMNS = (
    "match_id",
    "entity_id",
    "discipline_id",
    "discipline",
    "leaderboard_name",
    "rank_scope",
    "squad_place",
    "squad_name",
    "expected_athlete_count",
    "actual_athlete_count",
    "scored_athlete_count",
    "athlete_score_total_seconds",
    "squad_score_seconds",
    "difference",
    "reconciliation_status",
    "notes",
)


class MatchValidationError(RuntimeError):
    """Raised when parsed tables cannot be validated."""


@dataclass(frozen=True)
class ValidationResult:
    validation_summary_path: Path
    validation_findings_path: Path
    match_score_reconciliation_path: Path
    stage_score_reconciliation_path: Path
    squad_score_reconciliation_path: Path
    summary_rows: int
    finding_rows: int
    match_reconciliation_rows: int
    stage_reconciliation_rows: int
    squad_reconciliation_rows: int
    severity_counts: dict[str, int]


def validate_match(
    match_id: int,
    output_dir: Path | str,
    tolerance: float = TOLERANCE_SECONDS,
) -> ValidationResult:
    """Validate one match's parsed CSV tables."""
    output_path = Path(output_dir)
    tables_dir = output_path / "tables"
    validation_dir = output_path / "validation"

    match_scores = _read_csv(tables_dir / "match_scores.csv")
    rankings = _read_csv(tables_dir / "rankings.csv")
    squad_results = _read_csv(tables_dir / "squad_results.csv")
    stage_scores = _read_csv(tables_dir / "stage_scores.csv")
    _confirm_match_ids(
        match_id,
        match_scores,
        rankings,
        squad_results,
        stage_scores,
    )

    findings: list[dict[str, Any]] = []
    stage_groups = _group_stage_entries(stage_scores)
    match_reconciliation = _reconcile_match_scores(
        match_id,
        match_scores,
        stage_groups,
        findings,
        tolerance,
    )
    stage_reconciliation = _reconcile_stage_scores(
        match_id,
        stage_groups,
        findings,
        tolerance,
    )
    squad_reconciliation = _reconcile_squad_scores(
        match_id,
        squad_results,
        findings,
        tolerance,
    )
    _find_completeness_issues(match_id, match_scores, findings)
    _find_duplicate_entries(match_id, match_scores, findings)
    _find_fast_strings(match_id, stage_groups, findings)

    summary = _build_summary(match_id, findings)
    _ensure_directory(validation_dir)
    summary_path = validation_dir / "validation_summary.csv"
    findings_path = validation_dir / "validation_findings.csv"
    match_path = validation_dir / "match_score_reconciliation.csv"
    stage_path = validation_dir / "stage_score_reconciliation.csv"
    squad_path = validation_dir / "squad_score_reconciliation.csv"

    _write_csv(summary_path, SUMMARY_COLUMNS, summary)
    _write_csv(findings_path, FINDING_COLUMNS, findings)
    _write_csv(
        match_path,
        MATCH_RECONCILIATION_COLUMNS,
        match_reconciliation,
    )
    _write_csv(
        stage_path,
        STAGE_RECONCILIATION_COLUMNS,
        stage_reconciliation,
    )
    _write_csv(
        squad_path,
        SQUAD_RECONCILIATION_COLUMNS,
        squad_reconciliation,
    )

    severity_counts = Counter(row["severity"] for row in findings)
    return ValidationResult(
        validation_summary_path=summary_path,
        validation_findings_path=findings_path,
        match_score_reconciliation_path=match_path,
        stage_score_reconciliation_path=stage_path,
        squad_score_reconciliation_path=squad_path,
        summary_rows=len(summary),
        finding_rows=len(findings),
        match_reconciliation_rows=len(match_reconciliation),
        stage_reconciliation_rows=len(stage_reconciliation),
        squad_reconciliation_rows=len(squad_reconciliation),
        severity_counts={
            severity: severity_counts.get(severity, 0)
            for severity in ("ERROR", "WARNING", "REVIEW", "INFO")
        },
    )


def _reconcile_match_scores(
    match_id: int,
    match_scores: list[dict[str, str]],
    stage_groups: dict[tuple[str, ...], list[list[dict[str, str]]]],
    findings: list[dict[str, Any]],
    tolerance: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    occurrences: Counter[tuple[str, ...]] = Counter()

    for match_row in match_scores:
        key = _entry_key(match_row)
        occurrences[key] += 1
        occurrence = occurrences[key]
        groups = stage_groups.get(key, [])
        stages = groups[occurrence - 1] if occurrence <= len(groups) else []
        entity_id = _entry_entity_id(match_row, occurrence)
        stage_values = [
            value
            for value in (_number(row.get("stage_score_seconds")) for row in stages)
            if value is not None
        ]
        stage_total = sum(stage_values) if stage_values else None
        match_score = _number(match_row.get("match_score_seconds"))
        difference = (
            match_score - stage_total
            if match_score is not None and stage_total is not None
            else None
        )

        if match_score is None:
            status = "MISSING_MATCH_SCORE"
            notes = "Match score is missing."
            _add_finding(
                findings,
                match_id,
                "match_score_reconciliation",
                "ERROR",
                "missing_match_score",
                "athlete_discipline",
                entity_id,
                match_row,
                expected_value=stage_total,
                actual_value="",
                difference="",
                message=notes,
            )
        elif len(stage_values) < 4:
            status = "MISSING_STAGE_SCORES"
            notes = "Fewer than four scored stages are available."
            _add_finding(
                findings,
                match_id,
                "match_score_reconciliation",
                "ERROR",
                "missing_stage_scores",
                "athlete_discipline",
                entity_id,
                match_row,
                expected_value=4,
                actual_value=len(stage_values),
                difference=4 - len(stage_values),
                message=notes,
            )
        elif difference is not None and abs(difference) <= tolerance:
            status = "PASS"
            notes = "Match score reconciles to the four stage scores."
        elif _is_possible_procedural_adjustment(difference, tolerance):
            status = "MATCH_LEVEL_ADJUSTMENT"
            notes = (
                "Match score exceeds stage total; this may be a known "
                "match-level procedural penalty."
            )
            _add_finding(
                findings,
                match_id,
                "match_score_reconciliation",
                "INFO",
                "match_level_adjustment",
                "athlete_discipline",
                entity_id,
                match_row,
                expected_value=_clean_number(stage_total),
                actual_value=_clean_number(match_score),
                difference=_rounded(difference),
                message=notes,
            )
        else:
            status = "MISMATCH"
            notes = "Match score does not reconcile to stage total."
            _add_finding(
                findings,
                match_id,
                "match_score_reconciliation",
                "ERROR",
                "mathematical_mismatch",
                "athlete_discipline",
                entity_id,
                match_row,
                expected_value=_clean_number(stage_total),
                actual_value=_clean_number(match_score),
                difference=_rounded(difference),
                message=notes,
            )

        rows.append(
            {
                "match_id": match_id,
                "entity_id": entity_id,
                "athlete_id": match_row.get("athlete_id", ""),
                "athlete_name": match_row.get("athlete_name", ""),
                "team_name": match_row.get("team_name", ""),
                "discipline_id": match_row.get("discipline_id", ""),
                "discipline": match_row.get("discipline", ""),
                "entry_occurrence": occurrence,
                "stage_count": len(stages),
                "scored_stage_count": len(stage_values),
                "stage_total_seconds": _clean_number(stage_total),
                "match_score_seconds": _clean_number(match_score),
                "difference": _rounded(difference),
                "reconciliation_status": status,
                "notes": notes,
            }
        )

    return rows


def _reconcile_stage_scores(
    match_id: int,
    stage_groups: dict[tuple[str, ...], list[list[dict[str, str]]]],
    findings: list[dict[str, Any]],
    tolerance: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for groups in stage_groups.values():
        for occurrence, stages in enumerate(groups, start=1):
            for stage in stages:
                entity_id = _stage_entity_id(stage, occurrence)
                dropped_count = _integer(stage.get("dropped_string_count"))
                observed_count = (
                    5 - dropped_count if dropped_count is not None else None
                )
                stage_score = _number(stage.get("stage_score_seconds"))
                actual_average = _number(
                    stage.get("scored_avg_string_seconds")
                )
                expected_average = (
                    stage_score / 4 if stage_score is not None else None
                )
                average_difference = (
                    actual_average - expected_average
                    if actual_average is not None
                    and expected_average is not None
                    else None
                )

                if observed_count == 0 or stage_score is None:
                    status = "UNSCORED"
                    notes = "Stage has no scored non-zero string totals."
                    _add_finding(
                        findings,
                        match_id,
                        "stage_score_reconciliation",
                        "ERROR",
                        "unscored_stage",
                        "athlete_stage",
                        entity_id,
                        stage,
                        stage=stage,
                        expected_value=4,
                        actual_value=observed_count,
                        difference=(
                            4 - observed_count
                            if observed_count is not None
                            else ""
                        ),
                        message=notes,
                    )
                elif observed_count == 5:
                    status = "FOUR_FASTEST_USED"
                    notes = (
                        "Five non-zero totals were present; parser used "
                        "the four fastest."
                    )
                    _add_finding(
                        findings,
                        match_id,
                        "stage_score_reconciliation",
                        "WARNING",
                        "five_nonzero_totals",
                        "athlete_stage",
                        entity_id,
                        stage,
                        stage=stage,
                        expected_value=4,
                        actual_value=5,
                        difference=1,
                        message=notes,
                    )
                elif observed_count != 4:
                    status = "COUNTING_STRING_COUNT_ERROR"
                    notes = "Stage does not contain four counting strings."
                    _add_finding(
                        findings,
                        match_id,
                        "stage_score_reconciliation",
                        "ERROR",
                        "counting_string_count_mismatch",
                        "athlete_stage",
                        entity_id,
                        stage,
                        stage=stage,
                        expected_value=4,
                        actual_value=observed_count,
                        difference=(
                            observed_count - 4
                            if observed_count is not None
                            else ""
                        ),
                        message=notes,
                    )
                elif (
                    average_difference is not None
                    and abs(average_difference) > tolerance
                ):
                    status = "AVERAGE_MISMATCH"
                    notes = "Scored average does not equal stage score / 4."
                    _add_finding(
                        findings,
                        match_id,
                        "stage_score_reconciliation",
                        "ERROR",
                        "stage_average_mismatch",
                        "athlete_stage",
                        entity_id,
                        stage,
                        stage=stage,
                        expected_value=_rounded(expected_average, 4),
                        actual_value=_rounded(actual_average, 4),
                        difference=_rounded(average_difference, 4),
                        message=notes,
                    )
                else:
                    status = "PASS"
                    notes = (
                        "Four-counting-string structure and stage average "
                        "are internally consistent."
                    )

                rows.append(
                    {
                        "match_id": match_id,
                        "entity_id": entity_id,
                        "athlete_id": stage.get("athlete_id", ""),
                        "athlete_name": stage.get("athlete_name", ""),
                        "team_name": stage.get("team_name", ""),
                        "discipline_id": stage.get("discipline_id", ""),
                        "discipline": stage.get("discipline", ""),
                        "entry_occurrence": occurrence,
                        "stage_number": stage.get("stage_number", ""),
                        "stage_name": stage.get("stage_name", ""),
                        "expected_counting_string_count": 4,
                        "observed_nonzero_string_count": observed_count,
                        "stage_score_seconds": _clean_number(stage_score),
                        "expected_scored_avg_seconds": _rounded(
                            expected_average,
                            4,
                        ),
                        "actual_scored_avg_seconds": _clean_number(
                            actual_average
                        ),
                        "average_difference": _rounded(
                            average_difference,
                            4,
                        ),
                        "fastest_string_seconds": stage.get(
                            "fastest_string_seconds",
                            "",
                        ),
                        "penalty_count": stage.get("penalty_count", ""),
                        "reconciliation_status": status,
                        "notes": notes,
                    }
                )

    return rows


def _reconcile_squad_scores(
    match_id: int,
    squad_results: list[dict[str, str]],
    findings: list[dict[str, Any]],
    tolerance: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for squad in squad_results:
        entity_id = "|".join(
            (
                squad.get("discipline_id", ""),
                squad.get("rank_scope", ""),
                squad.get("squad_name", ""),
                squad.get("squad_place", ""),
            )
        )
        actual_count = _integer(squad.get("athlete_count")) or 0
        athlete_scores = [
            _number(squad.get(f"athlete_{number}_score"))
            for number in range(1, 5)
        ]
        scored_values = [value for value in athlete_scores if value is not None]
        athlete_total = sum(scored_values) if scored_values else None
        squad_score = _number(squad.get("squad_score_seconds"))
        difference = (
            squad_score - athlete_total
            if squad_score is not None and athlete_total is not None
            else None
        )

        if actual_count != 4:
            status = "NON_FOUR_PERSON_SQUAD"
            notes = "Squad does not list four athletes."
            _add_finding(
                findings,
                match_id,
                "squad_score_reconciliation",
                "WARNING",
                "non_four_person_squad",
                "squad",
                entity_id,
                squad,
                expected_value=4,
                actual_value=actual_count,
                difference=actual_count - 4,
                message=notes,
            )
        elif len(scored_values) != 4:
            status = "MISSING_ATHLETE_SCORE"
            notes = "One or more squad athlete scores are missing."
            _add_finding(
                findings,
                match_id,
                "squad_score_reconciliation",
                "ERROR",
                "missing_squad_athlete_score",
                "squad",
                entity_id,
                squad,
                expected_value=4,
                actual_value=len(scored_values),
                difference=4 - len(scored_values),
                message=notes,
            )
        elif difference is not None and abs(difference) > tolerance:
            status = "MISMATCH"
            notes = "Squad score does not equal listed athlete scores."
            _add_finding(
                findings,
                match_id,
                "squad_score_reconciliation",
                "ERROR",
                "squad_mathematical_mismatch",
                "squad",
                entity_id,
                squad,
                expected_value=_clean_number(athlete_total),
                actual_value=_clean_number(squad_score),
                difference=_rounded(difference),
                message=notes,
            )
        else:
            status = "PASS"
            notes = "Squad score reconciles to four athlete scores."

        rows.append(
            {
                "match_id": match_id,
                "entity_id": entity_id,
                "discipline_id": squad.get("discipline_id", ""),
                "discipline": squad.get("discipline", ""),
                "leaderboard_name": squad.get("leaderboard_name", ""),
                "rank_scope": squad.get("rank_scope", ""),
                "squad_place": squad.get("squad_place", ""),
                "squad_name": squad.get("squad_name", ""),
                "expected_athlete_count": 4,
                "actual_athlete_count": actual_count,
                "scored_athlete_count": len(scored_values),
                "athlete_score_total_seconds": _clean_number(athlete_total),
                "squad_score_seconds": _clean_number(squad_score),
                "difference": _rounded(difference),
                "reconciliation_status": status,
                "notes": notes,
            }
        )

    return rows


def _find_completeness_issues(
    match_id: int,
    match_scores: list[dict[str, str]],
    findings: list[dict[str, Any]],
) -> None:
    for occurrence, row in _rows_with_occurrence(match_scores):
        entity_id = _entry_entity_id(row, occurrence)
        for field, label in (
            ("athlete_name", "athlete name"),
            ("class", "class"),
        ):
            if not row.get(field, ""):
                _add_finding(
                    findings,
                    match_id,
                    "required_field_completeness",
                    "WARNING",
                    f"missing_{field}",
                    "athlete_discipline",
                    entity_id,
                    row,
                    expected_value=label,
                    actual_value="",
                    difference="",
                    message=f"Parsed entry is missing required {label}.",
                )


def _find_duplicate_entries(
    match_id: int,
    match_scores: list[dict[str, str]],
    findings: list[dict[str, Any]],
) -> None:
    counts = Counter(_entry_key(row) for row in match_scores)
    occurrences: Counter[tuple[str, ...]] = Counter()
    for row in match_scores:
        key = _entry_key(row)
        occurrences[key] += 1
        if counts[key] > 1 and occurrences[key] > 1:
            occurrence = occurrences[key]
            _add_finding(
                findings,
                match_id,
                "duplicate_entry_review",
                "WARNING",
                "duplicate_athlete_discipline",
                "athlete_discipline",
                _entry_entity_id(row, occurrence),
                row,
                expected_value=1,
                actual_value=counts[key],
                difference=counts[key] - 1,
                message=(
                    "Multiple parsed entries share the same athlete and "
                    "discipline identity; entries were preserved."
                ),
            )


def _find_fast_strings(
    match_id: int,
    stage_groups: dict[tuple[str, ...], list[list[dict[str, str]]]],
    findings: list[dict[str, Any]],
) -> None:
    for groups in stage_groups.values():
        for occurrence, stages in enumerate(groups, start=1):
            for stage in stages:
                fastest = _number(stage.get("fastest_string_seconds"))
                if fastest is None or fastest >= 1.20:
                    continue
                if fastest < 0.73:
                    finding_type = "fast_string_red_review"
                    message = (
                        "Fastest non-zero string is below 0.73 seconds; "
                        "strong manual review candidate."
                    )
                else:
                    finding_type = "fast_string_yellow_review"
                    message = (
                        "Fastest non-zero string is below 1.20 seconds; "
                        "manual review recommended."
                    )
                _add_finding(
                    findings,
                    match_id,
                    "fast_string_review",
                    "REVIEW",
                    finding_type,
                    "athlete_stage",
                    _stage_entity_id(stage, occurrence),
                    stage,
                    stage=stage,
                    expected_value=0.73 if fastest < 0.73 else 1.20,
                    actual_value=_clean_number(fastest),
                    difference=_rounded(
                        fastest - (0.73 if fastest < 0.73 else 1.20)
                    ),
                    message=message,
                )


def _build_summary(
    match_id: int,
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    definitions = (
        (
            "match_score_reconciliation",
            "ERROR",
            "Match final compared with four stage totals.",
        ),
        (
            "stage_score_reconciliation",
            "ERROR",
            "Four-string structure and stage average consistency.",
        ),
        (
            "squad_score_reconciliation",
            "ERROR",
            "Squad score compared with four listed athlete scores.",
        ),
        (
            "required_field_completeness",
            "WARNING",
            "Required athlete identity context in parsed match rows.",
        ),
        (
            "duplicate_entry_review",
            "WARNING",
            "Repeated athlete/discipline identities preserved for review.",
        ),
        (
            "fast_string_review",
            "REVIEW",
            "Fast strings are review items and do not invalidate scores.",
        ),
    )
    severity_order = {"ERROR": 4, "WARNING": 3, "REVIEW": 2, "INFO": 1}
    rows: list[dict[str, Any]] = []

    for check_name, severity, notes in definitions:
        check_findings = [
            row for row in findings if row["check_name"] == check_name
        ]
        severities = {row["severity"] for row in check_findings}
        if "ERROR" in severities:
            status = "FAIL"
        elif check_findings:
            status = "REVIEW"
        else:
            status = "PASS"
        summary_severity = max(
            severities or {severity},
            key=lambda value: severity_order[value],
        )
        rows.append(
            {
                "match_id": match_id,
                "check_name": check_name,
                "severity": summary_severity,
                "status": status,
                "finding_count": len(check_findings),
                "notes": notes,
            }
        )

    return rows


def _add_finding(
    findings: list[dict[str, Any]],
    match_id: int,
    check_name: str,
    severity: str,
    finding_type: str,
    entity_type: str,
    entity_id: str,
    row: dict[str, str],
    *,
    stage: dict[str, str] | None = None,
    expected_value: Any,
    actual_value: Any,
    difference: Any,
    message: str,
) -> None:
    findings.append(
        {
            "match_id": match_id,
            "check_name": check_name,
            "severity": severity,
            "finding_type": finding_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "athlete_name": row.get("athlete_name", ""),
            "team_name": row.get("team_name", ""),
            "discipline": row.get("discipline", ""),
            "stage_number": (stage or {}).get("stage_number", ""),
            "stage_name": (stage or {}).get("stage_name", ""),
            "expected_value": expected_value,
            "actual_value": actual_value,
            "difference": difference,
            "message": message,
        }
    )


def _group_stage_entries(
    stage_scores: list[dict[str, str]],
) -> dict[tuple[str, ...], list[list[dict[str, str]]]]:
    groups: dict[tuple[str, ...], list[list[dict[str, str]]]] = defaultdict(list)
    current: dict[tuple[str, ...], list[dict[str, str]]] = {}

    for row in stage_scores:
        key = _entry_key(row)
        if row.get("stage_number") == "1" or key not in current:
            group: list[dict[str, str]] = []
            groups[key].append(group)
            current[key] = group
        current[key].append(row)
    return groups


def _rows_with_occurrence(
    rows: list[dict[str, str]],
) -> Iterable[tuple[int, dict[str, str]]]:
    occurrences: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        key = _entry_key(row)
        occurrences[key] += 1
        yield occurrences[key], row


def _entry_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("athlete_id", ""),
        row.get("athlete_name", ""),
        row.get("team_name", ""),
        row.get("discipline_id", ""),
        row.get("discipline", ""),
    )


def _entry_entity_id(row: dict[str, str], occurrence: int) -> str:
    return "|".join(
        (
            row.get("athlete_id", ""),
            row.get("discipline_id", ""),
            str(occurrence),
        )
    )


def _stage_entity_id(row: dict[str, str], occurrence: int) -> str:
    return "|".join(
        (
            _entry_entity_id(row, occurrence),
            row.get("stage_number", ""),
        )
    )


def _confirm_match_ids(
    match_id: int,
    *tables: list[dict[str, str]],
) -> None:
    for rows in tables:
        unexpected = {
            row.get("match_id", "")
            for row in rows
            if row.get("match_id", "") != str(match_id)
        }
        if unexpected:
            raise MatchValidationError(
                f"Parsed tables contain unexpected match IDs: "
                f"{sorted(unexpected)}"
            )


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            return list(csv.DictReader(source))
    except FileNotFoundError as exc:
        raise MatchValidationError(f"Missing parsed table: {path}") from exc
    except (OSError, csv.Error) as exc:
        raise MatchValidationError(
            f"Could not read parsed table {path}: {exc}"
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
        raise MatchValidationError(
            f"Could not write validation table {path}: {exc}"
        ) from exc


def _ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MatchValidationError(
            f"Could not create validation directory {path}: {exc}"
        ) from exc
    if not path.is_dir():
        raise MatchValidationError(
            f"Validation path is not a directory: {path}"
        )


def _number(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_number(value: float | None) -> float | int | str:
    if value is None:
        return ""
    if value.is_integer():
        return int(value)
    return value


def _rounded(value: float | None, digits: int = 2) -> float | int | str:
    if value is None:
        return ""
    return _clean_number(round(value, digits))


def _is_possible_procedural_adjustment(
    difference: float | None,
    tolerance: float,
) -> bool:
    if difference is None or difference <= tolerance:
        return False
    penalty_units = difference / 3
    return abs(penalty_units - round(penalty_units)) <= tolerance
