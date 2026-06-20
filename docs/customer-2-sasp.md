# Customer 2: SASP Staff / Organization Framework

## Purpose

Develop a generic SASP validation, score audit, reporting, and analytics framework that could be used by SASP staff, match directors, or technology volunteers.

This customer stream should remain neutral and not Wilco-specific.

## Primary audience

- SASP staff
- Match directors
- Scorekeepers
- Technology committee / volunteers
- State and national event leadership

## Core questions

- Are the scores trustworthy before publication?
- Are squads complete and correctly scored?
- Do leaderboard totals reconcile with slot-level scoring?
- Are there missing strings, missing stages, DQ/DNF issues, or impossible times?
- Can match directors get a clean report without manually reviewing raw JSON?
- What national trends can be measured year over year?

## Important ranking clarification

For large matches such as Nationals:

- Individual High Overall / HOA awards are determined by Class, not Division.
- Squad rankings are always Divisional.
- Overall discipline leaderboards may rank everyone together, but award interpretation must preserve the official award scope.

Generic SASP reporting should expose rank type and award scope explicitly so reports do not confuse Overall comparison, Class-based HOA, gender context, and Divisional squad rankings.

## Generic SASP validation framework

### Validation categories

1. Mathematical Integrity
2. Completeness
3. Performance Anomaly Review
4. Squad Validation
5. Penalty Validation
6. DQ / DNF Handling
7. Hardcopy Reconciliation

### Severity levels

- RED: likely scoring or data integrity problem
- YELLOW: strong review candidate
- ORANGE: unusual performance, not necessarily wrong
- INFO: informational note

### Core checks

- Match total equals sum of four stage scores
- Stage score equals four counting strings
- Each stage has required strings
- Dropped string handling is valid
- Leaderboard score matches slot-level final score within tolerance
- Squad score equals sum of four athlete scores
- Squad has four contributing athletes
- Squad ranking scope is Divisional
- Individual HOA ranking scope is Class-based for large matches such as Nationals
- DQ and DNF records are handled separately
- Duplicate athlete / discipline entries are flagged
- Penalties reconcile with scored totals

## Generic SASP reporting framework

### Match summary

- Match name
- Match date
- Disciplines
- Entry counts
- Team counts
- Athlete counts
- Squad counts

### Results summary

- Overall discipline winners
- Class-based HOA winners
- Gender-context winners, where present
- Divisional squad winners
- Close finishes
- Participation statistics

### Squad results

- Discipline
- Divisional rank scope
- Squad name
- Place
- Score
- Athletes
- Individual scores

## Suggested Customer 2 workbooks

These workbook concepts are generic SASP-facing deliverables and should not include Wilco-specific coaching or team-development assumptions.

### SASP Match Integrity Workbook

Purpose: validate match quality before results are finalized.

Suggested tab order:

1. Dashboard
2. Score Audit Summary
3. Math Validation
4. Completeness Checks
5. String Anomalies
6. DQ / DNF Review
7. Squad Validation
8. Hardcopy Reconciliation
9. Warnings
10. Exception Log

### SASP Match Results Workbook

Purpose: produce neutral match result summaries.

Suggested tab order:

1. Match Summary
2. Participation Statistics
3. Athlete Results
4. Squad Results
5. Awards
6. Close Finishes
7. Match Records
8. Notes

### SASP Historical Analytics Workbook

Purpose: understand trends across years, matches, disciplines, cohorts, and participation levels.

Suggested tab order:

1. Dashboard
2. Participation Trends
3. Winner Thresholds
4. Award Thresholds
5. Field Medians
6. Compression Metrics
7. Difficulty Index
8. Improvement Velocity
9. Stage Difficulty
10. Discipline Trends
11. Year-over-Year Comparisons

## Generic SASP historical analytics

Historical analytics should use award-scope and field-size-aware benchmarks instead of fixed Top 1 / Top 3 / Top 5 / Top 10 cohorts.

Core benchmarks should always include Winner Threshold, Award Threshold, and Field Median.

Optional benchmarks should depend on cohort size:

- Use Top 10 Benchmark only when the cohort has 30 or more competitors.
- Use Top 25 Benchmark only when the cohort has 75 or more competitors.

Benchmark cohorts should follow award scope:

- Individual HOA uses Discipline plus Class.
- Gender context uses Discipline plus Class plus Gender when that board exists.
- Squad rankings use Discipline plus Division.
- Overall discipline comparison uses all competitors in the discipline.

Additional historical metrics may include Nationals Difficulty Index, Compression Index, Improvement Velocity, Stage Difficulty Index, Stage Separation Index, Participation Growth, and Discipline Trends.

## Hardcopy score sheet reconciliation

Future AI capability:

1. Upload photo, scan, or PDF of backup score sheet.
2. Extract strings and totals.
3. Compare to SASP system values.
4. Produce discrepancy report.

This should be treated as a review workflow, not an automatic override.

## Continue development here

Use this customer stream for generic SASP validation, match integrity, public match reporting, national analytics, and anything that could be shared with or proposed to SASP staff.
