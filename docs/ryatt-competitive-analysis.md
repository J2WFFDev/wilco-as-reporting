# Ryatt Competitive Analysis

## Purpose

The Ryatt Competitive Analysis report is a local-only competitive scouting
report for Ryatt West. It shows Ryatt's best historical score by discipline,
then lists Ryatt, competitors who are faster than Ryatt, and competitors within
a configurable slower-time gap.

This is not an official record report. It is a coaching and match-prep view
intended to help understand the competitive field around Ryatt.

## Command

```powershell
$env:PYTHONPATH = "src"
python -m wilco_as_reporting.cli ryatt-competitive-analysis --output-dir output
```

The default target is:

- athlete name: `Ryatt West`
- athlete ID: `76179`
- gap: `2.0` seconds
- match context: `671`

Optional arguments:

```powershell
python -m wilco_as_reporting.cli ryatt-competitive-analysis `
  --output-dir output `
  --target-athlete-id 76179 `
  --target-athlete-name "Ryatt West" `
  --gap-seconds 2.0 `
  --match-id 671
```

Use `--no-workbook` to create only the CSV outputs.

## Outputs

The command writes to:

`output/special_reports/ryatt_competitive_analysis/`

Files:

- `ryatt_competitive_analysis.csv`
- `ryatt_competitive_summary.csv`
- `ryatt_discipline_summary.csv`
- `data_quality_notes.csv`
- `ryatt_competitive_analysis.xlsx`

Workbook tabs:

1. Summary
2. Ryatt Competitive Analysis
3. Discipline Summary
4. Data Quality Notes

## Data source

The report uses local processed score files only. It recursively scans:

`output/<match_id>/tables/match_scores.csv`

It includes all locally available historical matches and all teams. It does not
call the SASP API, download JSON, scrape raw data, or rely only on
Wilco-specific history tables.

Blank athlete names and athlete ID `9999` are excluded. Rows without numeric
match scores are skipped.

## Gap logic

Lower score/time is better.

For each discipline where Ryatt has a local historical score:

1. Find Ryatt's best historical score.
2. Find every athlete's best historical score in that discipline.
3. Include:
   - Ryatt's own row
   - athletes faster than Ryatt
   - athletes within the configured slower-time gap
4. Exclude athletes slower than the configured gap.

The report calculates:

`gap_to_ryatt = competitor_best_score - ryatt_best_score`

Interpretation:

- negative gap = competitor is faster than Ryatt
- zero gap = same best score
- positive gap = competitor is slower than Ryatt

With the default `--gap-seconds 2.0`, the slower comparison group is labeled
`Within 2 Seconds Slower`. Other gap values use `Within Gap Slower`.

## Matching rules

Ryatt is matched by athlete ID first. If an athlete ID is missing, the report
falls back to normalized athlete name.

Competitor grouping also uses athlete ID when available, with normalized name
as fallback.

## Limitations

- The report only knows about locally processed match score files.
- Match dates are populated when `output/history/history_source_matches.csv`
  is available.
- It is a competitive scouting report, not a formal SASP record report.
- It does not create string, stage, or squad records.
