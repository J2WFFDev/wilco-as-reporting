# Repository Layout

This project uses a scalable Python package layout.

## Recommended structure

```text
wilco-as-reporting/
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
│       ├── api/
│       │   ├── __init__.py
│       │   └── sasp_client.py
│       ├── parsers/
│       │   ├── __init__.py
│       │   ├── slots_parser.py
│       │   └── leaderboard_parser.py
│       ├── validation/
│       │   ├── __init__.py
│       │   └── score_audit.py
│       ├── reports/
│       │   ├── __init__.py
│       │   ├── wilco_reports.py
│       │   └── sasp_reports.py
│       ├── analytics/
│       │   ├── __init__.py
│       │   └── historical_metrics.py
│       └── workbook/
│           ├── __init__.py
│           └── excel_writer.py
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

### `workbook/`

Create Excel workbooks from validated tables.

### `cli.py`

Command-line entry point for running the pipeline.

Example future command:

```powershell
python -m wilco_as_reporting.cli --match-id 664 --team-id 1894 --output-dir output/664
```

## Data flow

```text
SASP API
  -> raw JSON snapshots
  -> normalized tables
  -> validation tables
  -> report tables
  -> workbook / CSV outputs
```

## Design rule

Customer-specific report logic should not be mixed together.

- Customer 1: Wilco-specific coaching and team analytics.
- Customer 2: Generic SASP validation, reporting, and historical analytics.
