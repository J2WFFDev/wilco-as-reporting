# Wilco Analysis Workbook

## Purpose

The analysis workbook consolidates the most useful local historical, match,
ranking, capability, validation, and record views for Wilco Shooting Sports.
It is generated entirely from existing files under `output/`; the command does
not call the SASP API.

Lower score or time is better throughout the workbook. The configured Wilco
profile uses team key `wilco`, team name `Wilco Shooting Sports`, and team
number `1894`.

## Command

```powershell
$env:PYTHONPATH = "src"
python -m wilco_as_reporting.cli analysis-workbook `
  --team-key wilco `
  --match-id 664 `
  --output-dir output
```

If `--match-id` is omitted, the latest scored Wilco match in the local history
tables is selected. Historical views use the two most recent seasons by
default; change this with `--past-seasons`.

The workbook is written to:

`output/analysis/wilco_analysis_workbook.xlsx`

Matching CSV tables are written under `output/analysis/tables/`.

## Sheets

The workbook contains:

1. Cover
2. Wilco Match Score History
3. Athlete Perf by Discipline
4. All Teams by Match & Disc
5. Published SASP Rankings
6. Athlete Capability Matrix
7. Athlete Discipline Stage Values
8. Wilco vs Field by Discipline
9. Match Results
10. Wilco Stage Review
11. National Staff Validation
12. Records and PRs
13. Selected Match Highlights
14. Data Quality Notes

Several display names are shortened because Excel limits worksheet names to
31 characters. The matching CSV filenames retain the fuller view names.

## Selected match behavior

The selected match controls the Match Results, Wilco Stage Review, National
Staff Validation, and Selected Match Highlights sheets. Historical and field
comparison sheets continue to use the configured season window.

Match 664 is a scored validation match and populates the selected-match score
and stage views.

Match 671 may contain registrations and stage placeholders before Nationals
results are published. The workbook does not fail in that state. Entries are
retained, score cells remain blank, and the Data Quality Notes sheet clearly
identifies the no-score status.

## Records and benchmarks

Formal record views include personal records, recent PR highlights, Wilco
all-time records, and team season records from the existing records outputs.

Stage and string values are capability benchmarks only. They are useful for
coaching analysis but are not presented as formal stage, string, or squad
records.

## Wilco versus field

The Wilco versus field table compares aggregated scored entries by discipline.
Because lower times are better:

- a negative `avg_gap_to_field` means Wilco is faster than the field average;
- a negative `best_gap_to_field` means Wilco's best result is faster than the
  field's best result in the available data.

One bar chart compares Wilco and field average times by discipline.

## Limitations

- Results depend on locally available parsed, history, records, and validation
  outputs.
- Team IDs and complete squad counts are not available in the base match score
  tables.
- Published ranking rows may not contain athlete IDs or gender context.
- Missing schedules do not block analysis.
- Validation findings are review aids and do not automatically invalidate
  explainable scores.
- Blank athlete names and athlete ID `9999` are excluded by default.
- Configured athlete aliases are applied without modifying source files.
