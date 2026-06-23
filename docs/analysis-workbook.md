# Wilco Analysis Workbooks

## Purpose

The `analysis-workbook` command creates three separate workbook products from
local `output/` tables. The split keeps each workbook focused on one decision
context instead of mixing historical prep, Wilco match management, and match
staff review into one kitchen-sink file.

The command does not call the SASP API, download JSON, scrape raw data, or
modify source snapshots. It only reads existing local history, records, parsed
match, ranking, validation, and stage tables.

Business rules used throughout:

- team key: `wilco`
- team name: `Wilco Shooting Sports`
- team number: `1894`
- lower score/time is better
- seasons start September 1 and use `YY-YY Season` labels
- blank athlete names and athlete ID `9999` are excluded by default
- configured athlete aliases are applied without modifying source files
- string, stage, and squad records are not formal records
- stage/string values may appear as capability benchmarks only

## Command

Default output is the historical prep workbook:

```powershell
$env:PYTHONPATH = "src"
python -m wilco_as_reporting.cli analysis-workbook `
  --team-key wilco `
  --match-id 664 `
  --output-dir output
```

Choose a product with `--view-set`:

```powershell
python -m wilco_as_reporting.cli analysis-workbook --team-key wilco --match-id 664 --output-dir output --view-set historical-prep
python -m wilco_as_reporting.cli analysis-workbook --team-key wilco --match-id 664 --output-dir output --view-set wilco-match
python -m wilco_as_reporting.cli analysis-workbook --team-key wilco --match-id 664 --output-dir output --view-set staff-match
python -m wilco_as_reporting.cli analysis-workbook --team-key wilco --match-id 664 --output-dir output --view-set all
```

`--view-set all` builds all three workbooks in one run. Matching source CSVs
for visible workbook tabs are written under `output/analysis/tables/`.

## Workbook 1: Historical records and match prep

Path:

`output/analysis/historical_prep/wilco_historical_records_prep.xlsx`

Use this for Wilco historical records, athlete preparation, and match prep. It
contains only Wilco-scoped historical and prep views:

1. Cover
2. Wilco Historical Score History
3. Athlete Perf by Discipline
4. Athlete Capability Matrix
5. Wilco vs Field by Discipline
6. Records and PRs
7. Data Quality Notes

The historical workbook intentionally does not include Published SASP Rankings,
selected-match results, match review, national staff validation, or the
long-format athlete discipline stage values sheet. Long-format stage values are
written to CSV only at:

`output/analysis/tables/athlete_discipline_stage_values.csv`

## Workbook 2: Wilco match management

Path:

`output/analysis/wilco_match/wilco_match_management_<match_id>.xlsx`

Use this for Wilco match management and results with record/PR context for one
selected match. It contains:

1. Cover
2. Wilco Match Results
3. Wilco Stage Review
4. Match Records and PRs
5. Coach Review Queue
6. Data Quality Notes

Match 671 can be generated before scores are published. In that no-score state,
the workbook does not fail; score cells remain blank where appropriate and Data
Quality Notes identifies the selected match as no-score/participation context.

## Workbook 3: Staff match review

Path:

`output/analysis/staff_match/staff_match_review_<match_id>.xlsx`

Use this for Nationals staff or match-director review of one selected match. It
contains:

1. Cover
2. All Competitor Match Results
3. Published Ranking Detail
4. Validation Findings
5. Field by Discipline
6. Records Match Bests
7. Data Quality Notes

Published Ranking Detail belongs only in this staff view because its value is
rank context: rank type, rank scope, field size, percentile, margins, and source
file. Those details are useful for audit/review but are too noisy for Wilco
historical prep.

The Excel tab is named `Records Match Bests` because Excel worksheet names
cannot contain `/`.

## CSV support and large tables

For every visible workbook tab, the command writes a source CSV to:

`output/analysis/tables/`

The command also writes full long-form support tables when they are useful but
not appropriate as workbook tabs, including:

- `athlete_discipline_stage_values.csv`
- `all_historical_match_scores_full.csv`

Excel sheets are limited to 1,048,576 rows. The command does not silently sample
data. If a table is too large for Excel, the complete table remains in CSV, the
workbook notes the full source row count and row-limit condition, and the sheet
only contains the Excel-safe visible portion.

## Limitations

- Results depend on locally available generated `output/` tables.
- Missing schedules do not block workbook generation.
- Validation findings are review aids and do not automatically invalidate
  explainable scores.
- Some requested tab labels are shortened to satisfy Excel's 31-character sheet
  name limit.
