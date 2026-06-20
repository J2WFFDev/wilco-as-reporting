# Codex Master Prompt

Use this prompt when starting Codex work on this repository.

---

You are working in the repository `J2WFFDev/wilco-as-reporting`.

This project builds SASP match reporting and validation tools using public SASP JSON API data.

There are two customers:

## Customer 1: Wilco Shooting Sports

Build Wilco-specific reporting for coaching, athlete development, match execution, Nationals readiness, and team communication.

Primary outputs:

- Wilco Match Operations workbook
- Stage Coach View
- Athlete Stage Matrix
- Squad Report
- Wilco vs Field
- Match Records
- Highlights
- Match Results story package
- Historical Wilco analytics

## Customer 2: SASP staff / organization

Build a generic, neutral framework for validation, score audit, public match reporting, and national analytics.

Primary outputs:

- Score validation framework
- Hardcopy score sheet reconciliation design
- Generic match summary
- Squad validation
- National year-over-year analytics
- Podium threshold and difficulty metrics

## Data sources

Use API-first data access.

Slots:

```text
https://virtual.sssfonline.com/api/shot/SASP/competitions/{match_id}/slots
```

Leaderboard:

```text
https://virtual.sssfonline.com/api/shot/sasp-leaderboard/{match_id}
```

Competition list:

```text
https://virtual.sssfonline.com/api/shot/SASP/competitions?type=S&page=1
```

Known team/entity:

```text
Wilco Shooting Sports = 1894
```

Known match IDs:

```text
664 = 2026 Texas State SASP Championship Match
671 = 2026 SASP National Championships
```

## Development rules

1. Fetch raw API data and save JSON snapshots before parsing.
2. Do not modify raw snapshots.
3. Normalize data into clean tables.
4. Validate scores before reporting.
5. Keep Wilco-specific logic separate from generic SASP logic.
6. Keep report tables readable and coach-usable.
7. Keep audit/detail tables available but not front-facing.

## Initial implementation goal

Create a first working pipeline that accepts a `match_id` and generates output for that match.

Example:

```powershell
python -m wilco_as_reporting.cli --match-id 664 --team-id 1894 --output-dir output/664
```

Expected stages:

1. Fetch API JSON.
2. Save raw snapshots.
3. Parse slots data.
4. Parse leaderboard data.
5. Create validation tables.
6. Create Wilco report tables.
7. Create generic SASP report tables.
8. Create Excel workbook.

## Initial output files

```text
output/{match_id}/raw/{match_id}_slots.json
output/{match_id}/raw/{match_id}_leaderboard.json
output/{match_id}/tables/match_scores.csv
output/{match_id}/tables/stage_string_scores.csv
output/{match_id}/tables/stage_summary.csv
output/{match_id}/tables/rankings.csv
output/{match_id}/tables/squad_results.csv
output/{match_id}/tables/squad_members.csv
output/{match_id}/tables/match_records.csv
output/{match_id}/tables/highlights.csv
output/{match_id}/tables/score_audit_flags.csv
output/{match_id}/tables/wilco_vs_field.csv
output/{match_id}/wilco_match_report.xlsx
```

## Important scoring decisions

- Use `spp*_tot*` for official scored strings.
- Ignore zeros in `spp*_tot*` for fastest string and average counting string calculations because zero usually represents a dropped string.
- Stage Score = sum of the four counting `spp*_tot*` values.
- Scored Avg String = Stage Score / 4.
- Preserve raw strings and penalties for audit.
- Use leaderboard data for rank/place and squad results.
- Use slots data for athlete IDs and string-level data.

## Highlight quality rules

Do not generate duplicate highlights just because an athlete appears in multiple leaderboard views.

Collapse by:

- Athlete
- Discipline
- Score

Use clean narrative categories:

- Overall Champion
- Overall Runner-Up
- Close to Overall Win
- Overall Top 5
- Division Winner
- Gender Winner
- Podium / Award
- Near Award Miss
- Photo Finish
- Squad Podium
- Squad Near Miss
- Team Best
- Personal Record
- Team Record

Near Award Miss should only apply when the athlete or squad finished outside award places but within the configured margin of the award cutoff.

## Match Records

For each actual stage name, report only:

- Fastest Individual String
- Fastest Stage Score

Do not include string number in user-facing output.

## Keep documentation updated

When implementing features, update the relevant file in `docs/` so the architecture stays understandable.
