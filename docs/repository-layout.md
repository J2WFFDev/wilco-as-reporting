# Repository Layout

This project uses a scalable Python package layout.

## Recommended structure

```text
wilco-as-reporting/
│
├── .github/
│   └── workflows/
│       ├── fetch-match.yml
│       ├── discover-matches.yml
│       ├── refresh-match.yml
│       ├── build-match-report.yml
│       ├── build-team-match-report.yml
│       ├── build-nationals-ops.yml
│       ├── backfill-matches.yml
│       └── incremental-refresh.yml
│
├── config/
│   ├── match_overrides.csv
│   ├── watched_matches.csv
│   └── team_profiles.csv
│
├── docs/
│   ├── customer-1-wilco.md
│   ├── customer-2-sasp.md
│   ├── data-sources.md
│   ├── metrics-and-validation.md
│   ├── report-packages.md
│   ├── repository-layout.md
│   ├── project-philosophy.md
│   └── codex-master-prompt.md
│
├── src/
│   └── wilco_as_reporting/
│       ├── __init__.py
│       ├── cli.py
│       ├── discovery.py
│       ├── pipeline.py
│       ├── nationals_ops.py
│       ├── batch_refresh.py
│       ├── refresh_manifest.py
│       ├── team_profiles.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── sasp_client.py
│       ├── parsers/
│       │   ├── __init__.py
│       │   ├── slots_parser.py
│       │   └── leaderboard_parser.py
│       ├── validators/
│       │   ├── __init__.py
│       │   └── score_validator.py
│       ├── reports/
│       │   ├── __init__.py
│       │   ├── match_report.py
│       │   └── team_report.py
│       ├── analytics/
│       │   ├── __init__.py
│       │   └── historical_metrics.py
│       └── workbooks/
│           ├── __init__.py
│           ├── excel_writer.py
│           ├── team_excel_writer.py
│           └── nationals_excel_writer.py
│
├── data/
│   ├── raw/
│   └── processed/
│
├── output/
│
├── tests/
│
├── requirements.txt
├── README.md
└── .gitignore
```

## Module responsibilities

### `api/`

Fetch data from SASP API endpoints and save raw JSON snapshots.

### `discovery.py`

Paginate the competition list endpoint, preserve raw page snapshots, flatten
the discovered match catalog, and apply curated include/exclude overrides.

### `parsers/`

Convert raw SASP JSON into normalized table data.

### `validation/`

Run score integrity checks before reporting.

### `reports/`

Build customer-specific reporting tables.

- `wilco_reports.py` should contain Wilco-specific coaching and team reporting logic.
- `sasp_reports.py` should contain neutral, generic SASP reporting logic.

### `analytics/`

Build historical and competitive benchmark metrics.

### `workbooks/`

Create Excel workbooks from validated tables.

### `pipeline.py`

Run the fetch, parse, validate, report-table, and workbook steps in order for
one match.

### `nationals_ops.py`

Preserve timestamped team-build snapshots, append the runtime refresh
manifest, compare the current team state with the previous snapshot, and
build the Nationals change tables and daily brief.

### `batch_refresh.py`

Select bounded historical or watched/recent match sets, write dry-run plans,
execute requested processing levels, record per-match results/errors, and
skip unchanged heavy processing when hashes match.

### `refresh_manifest.py`

Own the canonical runtime manifest schema, migration from the earlier
snapshot manifest, current-state upserts, and stable file/directory hashes.

### `team_profiles.py`

Load tracked team identity, aliases, and activation metadata used by
team-focused reports.

### `cli.py`

Command-line entry point for running the pipeline.

Example future command:

```powershell
python -m wilco_as_reporting.cli --match-id 664 --team-id 1894 --output-dir output/664
```

Current acquisition commands:

```powershell
python -m wilco_as_reporting.cli --match-id 664 --output-dir output/664 --overwrite
python -m wilco_as_reporting.cli discover --output-dir output/discovery --overwrite
```

Current single-match processing commands:

```powershell
python -m wilco_as_reporting.cli parse --match-id 664 --output-dir output/664
python -m wilco_as_reporting.cli validate --match-id 664 --output-dir output/664
python -m wilco_as_reporting.cli report --match-id 664 --output-dir output/664
python -m wilco_as_reporting.cli workbook --match-id 664 --output-dir output/664
python -m wilco_as_reporting.cli build --match-id 664 --output-dir output/664 --include-schedule
python -m wilco_as_reporting.cli team-report --match-id 664 --output-dir output/664 --team-key wilco
python -m wilco_as_reporting.cli team-workbook --match-id 664 --output-dir output/664 --team-key wilco
python -m wilco_as_reporting.cli build-team --match-id 664 --output-dir output/664 --team-key wilco --include-schedule
python -m wilco_as_reporting.cli build-nationals --match-id 671 --output-dir output/671 --team-key wilco --include-schedule --overwrite --snapshot-label manual
python -m wilco_as_reporting.cli backfill --match-ids 628,664,671 --team-key wilco --output-dir output --include-schedule --dry-run
python -m wilco_as_reporting.cli incremental-refresh --team-key wilco --output-dir output --lookback-days 14 --include-watched --include-schedule --dry-run
```

## Data flow

```text
SASP API
  -> raw JSON snapshots
  -> normalized tables
  -> validation tables
  -> report tables
  -> team workbook / CSV outputs
  -> timestamped snapshot
  -> change tables / daily brief / Nationals operations workbook
```

## Design rule

Customer-specific report logic should not be mixed together.

- Customer 1: Wilco-specific coaching and team analytics.
- Customer 2: Generic SASP validation, reporting, and historical analytics.
