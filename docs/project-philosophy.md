# Project Philosophy

## Purpose

This project exists to turn SASP match data into reliable validation, useful reporting, and actionable analytics.

It serves two different customers:

1. Wilco Shooting Sports internal coaching and operations.
2. SASP staff / organization-level validation and reporting concepts.

Those customers overlap in data sources but not in purpose.

## Principles

### 1. Validation before reporting

Reports should be generated from validated tables. Score audit should happen before highlights, narratives, or historical analytics.

### 2. Preserve raw data

Raw API JSON should be saved as snapshots and never modified.

### 3. Separate customer logic

Wilco-specific coaching logic should remain separate from generic SASP reporting and validation logic.

### 4. Coach usability over raw complexity

Wilco-facing reports should be useful to coaches during and after matches, not just technically complete.

### 5. Story quality over leaderboard duplication

Highlights should summarize a performance once, even if the athlete appears in multiple leaderboard views.

### 6. Award scope must be preserved

For large matches such as Nationals:

- Individual HOA awards are Class-based.
- Squad rankings are Divisional.
- Overall discipline boards are comparison views unless otherwise specified.

### 7. Metrics should be cohort-aware

Avoid universal Top 1 / Top 3 / Top 5 / Top 10 assumptions. Use Winner Threshold, Award Threshold, Field Median, and optional cohort-size-based benchmarks.

### 8. Official metrics and analysis metrics are different

Official stage metrics should use the four counting strings. Consistency metrics can use raw five-string data, but should be labeled as analysis metrics.

### 9. Warnings are not failures by default

Performance anomalies should be reviewed, not automatically treated as errors.

### 10. Build small first

The first working pipeline should fetch one match, parse a small set of tables, and validate the data before building full workbooks or advanced analytics.

## First implementation target

Match ID `664` should be used as the first test case.

Minimum useful outputs:

- `match_scores.csv`
- `rankings.csv`
- `squad_results.csv`

After those are correct, add validation and workbook generation.
