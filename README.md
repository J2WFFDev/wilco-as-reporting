# Wilco AS Reporting

Local-first SASP data acquisition, validation, reporting, historical analytics,
records, and coach-planning tools for Wilco Shooting Sports.

The repository also preserves generic SASP validation and match-reporting
layers that are not tied to Wilco.

## Quick Start

Use Python 3.11 or newer and install the tracked dependencies:

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
```

The recommended local production sequence is:

```powershell
# 1. Discover available matches
python -m wilco_as_reporting.cli discover --output-dir output/discovery

# 2. Download selected raw snapshots conservatively
python -m wilco_as_reporting.cli download-raw --match-ids 628,664,671 --output-dir output --include-schedule --skip-existing

# 3. Review local raw coverage
python -m wilco_as_reporting.cli raw-status --output-dir output --match-ids 628,664,671

# 4. Build or refresh selected historical matches
python -m wilco_as_reporting.cli backfill --match-ids 628,664,671 --team-key wilco --output-dir output --dry-run

# 5. Build historical data and coach insights
python -m wilco_as_reporting.cli history-build --team-key wilco --output-dir output
python -m wilco_as_reporting.cli history-insights --team-key wilco --output-dir output

# 6. Build records and Nationals planning packages
python -m wilco_as_reporting.cli records-build --team-key wilco --output-dir output
python -m wilco_as_reporting.cli nationals-readiness --team-key wilco --match-id 671 --output-dir output
python -m wilco_as_reporting.cli nationals-packet --team-key wilco --match-id 671 --output-dir output
```

Review a backfill dry-run before using an explicit `--build-level`. Do not run
unbounded historical refreshes.

## Workbooks to Open

For the current Nationals coaching workflow, open this first:

```text
output/nationals_packet/wilco_671_nationals_coach_packet.xlsx
```

Supporting workbooks include:

- `output/nationals_readiness/wilco_671_nationals_readiness.xlsx`
- `output/records/wilco_records_report.xlsx`
- `output/history/wilco_history_insights.xlsx`
- `output/history/wilco_history_report.xlsx`

For an individual match, use the generated workbook under
`output/<match_id>/workbooks/`.

All files under `output/` are generated local artifacts. The folder is
intentionally ignored by Git and must not be committed.

## Main Commands

### Acquisition and refresh

- `discover`: build raw and curated match indexes.
- `fetch`: fetch one match's raw snapshots.
- `download-raw`: paced desktop downloader for selected match IDs.
- `raw-status`: inventory useful local raw JSON.
- `backfill`: guarded historical build for selected matches.
- `incremental-refresh`: refresh watched, active, and recent matches.

### Single-match processing

- `parse`: create normalized base tables.
- `validate`: create score reconciliation and finding tables.
- `report`: create report-ready CSV tables.
- `workbook`: build the generic match workbook.
- `build`: run the generic fetch-to-workbook pipeline.
- `team-report`: build Wilco-focused match tables.
- `team-workbook`: build the Wilco match workbook.
- `build-team`: run the full Wilco match pipeline.
- `build-nationals`: refresh, snapshot, compare, and report Nationals
  operations.

### Historical and coach planning

- `history-build`: create the stable Wilco historical layer.
- `history-insights`: create coach-facing trends and confidence flags.
- `records-build`: create Wilco records and personal-record tables.
- `nationals-readiness`: build the private Match 671 readiness brief.
- `nationals-packet`: build the concise Nationals coach meeting packet.

There is currently no `analysis-workbook` command.

## Configuration

- `config/team_profiles.csv`: team identity and aliases.
- `config/athlete_aliases.csv`: curated athlete identity variants.
- `config/match_overrides.csv`: discovery include/exclude overrides.
- `config/watched_matches.csv`: monitored-match refresh settings.

## GitHub Actions

Manual workflows remain available for discovery, raw fetch/refresh, match and
team builds, Nationals operations, backfill, and incremental refresh. Local
desktop commands are the primary path for historical analytics, records,
readiness, and coach-packet generation.

See [docs/repo-inventory.md](docs/repo-inventory.md) for the production
inventory and workflow purpose of each tracked file group.

## Documentation

- [Data sources](docs/data-sources.md)
- [Refresh strategy](docs/refresh-strategy.md)
- [Metrics and validation](docs/metrics-and-validation.md)
- [Report packages](docs/report-packages.md)
- [Historical analytics](docs/historical-analytics.md)
- [Records report](docs/records-report.md)
- [Nationals readiness](docs/nationals-readiness.md)
- [Nationals coach packet](docs/nationals-coach-packet.md)
- [Repository layout](docs/repository-layout.md)
- [Repository inventory](docs/repo-inventory.md)

## Core Rules

- Preserve raw snapshots.
- Validate before reporting.
- Lower SASP time is better.
- Keep Class and Division award scopes separate.
- Treat Match 671 no-score data as participation context only.
- Keep coach-private notes separate from public-safe content.
