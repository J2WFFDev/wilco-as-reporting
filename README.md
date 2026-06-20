# Wilco AS Reporting

Analytics and reporting framework for SASP match data.

This repository is being structured for two related customers:

1. **Customer 1: Wilco Shooting Sports internal use**  
   Coach-focused reporting, match operations, athlete development, Nationals preparation, and Wilco-specific historical analytics.

2. **Customer 2: SASP staff / organization use**  
   Generic validation, score audit, match reporting, and national analytics concepts that could be adapted beyond Wilco.

## Current data sources

SASP data is available through public JSON API endpoints:

```text
Slots:
https://virtual.sssfonline.com/api/shot/SASP/competitions/{match_id}/slots

Leaderboard:
https://virtual.sssfonline.com/api/shot/sasp-leaderboard/{match_id}

Competition list:
https://virtual.sssfonline.com/api/shot/SASP/competitions?type=S&page=1
```

Known match IDs:

| Match ID | Match |
|---:|---|
| 664 | 2026 Texas State SASP Championship Match |
| 671 | 2026 SASP National Championships |

## Project direction

The project should develop in layers:

```text
Raw SASP API JSON
  -> Raw JSON snapshots
  -> Score validation / audit tables
  -> Clean normalized reporting tables
  -> Wilco operations workbook
  -> Wilco results package
  -> SASP generic reporting / analytics framework
```

## Documentation

Start here:

- [`docs/customer-1-wilco.md`](docs/customer-1-wilco.md)
- [`docs/customer-2-sasp.md`](docs/customer-2-sasp.md)
- [`docs/data-sources.md`](docs/data-sources.md)
- [`docs/report-packages.md`](docs/report-packages.md)
- [`docs/metrics-and-validation.md`](docs/metrics-and-validation.md)
- [`docs/codex-master-prompt.md`](docs/codex-master-prompt.md)

## Key rule

Validation comes before reporting. Reports should trust validated score tables, not independently interpret raw JSON each time.

## Single-match pipeline

Run each processing stage independently:

```powershell
python -m wilco_as_reporting.cli parse --match-id 664 --output-dir output/664
python -m wilco_as_reporting.cli validate --match-id 664 --output-dir output/664
python -m wilco_as_reporting.cli report --match-id 664 --output-dir output/664
python -m wilco_as_reporting.cli workbook --match-id 664 --output-dir output/664
```

Or run the full fetch-to-workbook pipeline:

```powershell
python -m wilco_as_reporting.cli build --match-id 664 --output-dir output/664 --include-schedule
```

The manual GitHub Actions workflow **Build Match Report** uploads
`match-<match_id>-report`, containing raw snapshots, parsed tables, validation
outputs, report tables, and the Excel workbook.

All files under `output/` are generated artifacts and remain ignored by Git.

## Wilco coaching report

Team profiles are configured in `config/team_profiles.csv`. Build the Wilco
coach package with:

```powershell
python -m wilco_as_reporting.cli team-report --match-id 664 --output-dir output/664 --team-key wilco
python -m wilco_as_reporting.cli team-workbook --match-id 664 --output-dir output/664 --team-key wilco
python -m wilco_as_reporting.cli build-team --match-id 664 --output-dir output/664 --team-key wilco --include-schedule
```

The full-match report answers what happened across the match. The Wilco
package filters and translates those results into team summaries, athlete
results, awards, squads, stage coaching cues, and a coach-readable review
queue.

The manual GitHub Actions workflow **Build Team Match Report** uploads
`match-<match_id>-<team_key>-report`. Match `664` is the completed validation
match; Match `671` is the Nationals readiness and live-monitoring target.

## Nationals operations

Refresh Match `671`, preserve a timestamped Wilco snapshot, compare it with
the prior snapshot, and create the daily operations brief with:

```powershell
python -m wilco_as_reporting.cli build-nationals --match-id 671 --output-dir output/671 --team-key wilco --include-schedule --overwrite --snapshot-label manual
```

Snapshots are stored under
`output/<match_id>/snapshots/<YYYYMMDD_HHMMSS>_<team_key>_<label>/`.
Runtime refresh history is appended to
`output/state/match_refresh_manifest.csv`. The current comparison tables and
daily brief are written under
`output/<match_id>/nationals_ops/<team_key>/`, and the coach workbook is
`output/<match_id>/workbooks/match_<match_id>_<team_key>_nationals_ops.xlsx`.

The manual **Build Nationals Ops Report** workflow uploads
`nationals-<match_id>-<team_key>-ops` with the complete current build,
timestamped snapshot, operations tables, workbook, and manifest. Partial live
Nationals data is reported clearly and does not fail the build. The workflow
restores the latest snapshot/manifest state from a match-and-team-scoped
Actions cache so separate manual runs can compare safely. Scheduled automation
is intentionally not included yet.
