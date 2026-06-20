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

Build API foundation first, then parsing, then validation, then reports. Do not jump directly to Excel, highlights, or historical analytics before raw data access and basic parsing are reliable.

## Current implementation process

The active process is:

```text
1. Discover matches
2. Filter usable matches
3. Fetch selected match data
4. Save raw snapshots
5. Parse clean tables
6. Validate scores
7. Generate reports and artifacts
```

## API foundation phases

Before parsing begins, the API foundation should be completed in small steps:

```text
Phase 2A.1 — API fetch and raw snapshots
Phase 2A.2 — GitHub Actions runner
Phase 2A.3 — Match discovery and match index
```

### Phase 2A.1

Fetch known match data by match ID and save immutable raw snapshots.

### Phase 2A.2

Run the fetch pipeline in GitHub Actions so local Python is not required.

### Phase 2A.3

Use the competition list API to discover matches, paginate results, filter test matches, and build a match index.

## Live-event refresh

Nationals match `671` is a monitoring target rather than a one-time download.
The raw slots, leaderboard, and optional schedule snapshots should support
repeated refresh while registration and results are changing during the
event. Refreshing raw snapshots does not replace the later parsing,
validation, or reporting phases.

Watched-match selection, recent-match refresh rules, change detection, and the
future refresh manifest are defined in
[`refresh-strategy.md`](./refresh-strategy.md).

## First implementation target

Match ID `664` should be used as the first test case.

Minimum useful parsing outputs after the API foundation is proven:

- `match_scores.csv`
- `rankings.csv`
- `squad_results.csv`

After those are correct, add validation and workbook generation.
