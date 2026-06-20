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

- Overall winners
- Division winners
- Gender winners
- Squad winners
- Close finishes
- Participation statistics

### Squad results

- Discipline
- Rank scope
- Squad name
- Place
- Score
- Athletes
- Individual scores

## Generic SASP historical analytics

Potential national-level metrics:

- Podium Thresholds
- Nationals Difficulty Index
- Compression Index
- Improvement Velocity
- Stage Difficulty Index
- Stage Separation Index
- Participation Growth
- Discipline Trends
- Year-over-Year Top 1 / Top 3 / Top 5 / Top 10 medians

## Hardcopy score sheet reconciliation

Future AI capability:

1. Upload photo, scan, or PDF of backup score sheet.
2. Extract strings and totals.
3. Compare to SASP system values.
4. Produce discrepancy report.

This should be treated as a review workflow, not an automatic override.

## Continue development here

Use this customer stream for generic SASP validation, match integrity, public match reporting, national analytics, and anything that could be shared with or proposed to SASP staff.
