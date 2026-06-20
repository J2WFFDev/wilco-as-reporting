# Report Packages

## Report table layer

Parsed and validated match data should be converted into report-ready CSV
tables before workbook generation:

```powershell
python -m wilco_as_reporting.cli report --match-id 664 --output-dir output/664
```

The command writes `output/<match_id>/report_tables/` with team, athlete,
award, squad, stage-performance, validation-rollup, and coach-review tables.
These tables provide a stable input layer for a future Excel workbook.

The report table layer does not create highlights, historical analytics, or
Excel files. Workbook generation should consume these report-ready tables only
after parsing and validation have completed.

`team_summary.csv` contains one row per team represented in the match.
Official individual award placements retain Class scope, squads retain
Division scope, and overall discipline comparison rows remain explicitly
marked with `award_scope = Comparison`.

## Workbook generation

Build the Excel workbook after report tables are available:

```powershell
python -m wilco_as_reporting.cli workbook --match-id 664 --output-dir output/664
```

The workbook is written to:

```text
output/<match_id>/workbooks/match_<match_id>_report.xlsx
```

It contains Cover, Team Summary, Athlete Summary, Award Results, Squad
Summary, Stage Performance, Coach Review Queue, and Validation Rollup tabs.
The workbook is a generated artifact, not source-controlled data.

## End-to-end single-match build

Run the full single-match pipeline with:

```powershell
python -m wilco_as_reporting.cli build --match-id 664 --output-dir output/664 --include-schedule
```

The command fetches raw snapshots, parses base tables, validates scores,
builds report tables, and creates the workbook. Validation findings with
severity `ERROR` are included in the artifact and do not by themselves fail
the pipeline.

The GitHub Actions workflow **Build Match Report** runs the same pipeline
without local Python. Its `match-<match_id>-report` artifact contains raw JSON
snapshots, parsed tables, validation outputs, report tables, and the workbook.
Artifacts use a 14-day retention period.

All generated files remain under ignored `output/` paths and must not be
committed.

## Award and ranking scope rules

For large matches such as Nationals:

- Individual High Overall / HOA awards are determined by Class, not Division.
- Squad rankings are always Divisional.
- Overall discipline boards may rank all competitors together and are useful for comparison, but they should not be confused with the Class-based HOA award structure.

Report logic must keep these scopes separate:

| Result Type | Correct Award Scope |
|---|---|
| Individual HOA / High Overall | Class |
| Individual gender HOA, when present | Class plus gender context |
| Squad rankings | Division |
| Overall discipline comparison | All competitors in discipline |

## Customer 1: Wilco report packages

These packages are Wilco-specific and should not be presented as generic SASP deliverables.

### Package 1: Wilco Match Operations Package

Customer: Wilco Shooting Sports.

Purpose: help coaches prepare, execute, and review matches.

Core tables:

- Registered Athletes
- Match Scores
- Rankings
- Stage Coach View
- Athlete Stage Matrix
- Squad Report
- Squad Members
- Wilco vs Field
- Match Records
- Highlights
- Score Audit Summary

Stage Coach View columns:

- Athlete Name
- Discipline
- Stage Name
- Fastest String
- Scored Avg String
- Stage Score
- Best Historical Stage Score
- Avg Historical Stage Score
- Coach Cue

Use four counting strings for official stage metrics.

Athlete Stage Matrix columns:

- Athlete Name
- Discipline
- Stage Name
- Fastest String
- Avg String
- Fastest Stage Score
- Avg Stage Score
- Best Match Score
- Avg Match Score

Match Records should include only meaningful records:

- Fastest Individual String by stage
- Fastest Stage Score by stage
- Lowest Match Score by discipline
- Closest Finish

Do not include derived records such as fastest average match pace.

### Package 2: Wilco Match Results and Story Package

Customer: Wilco Shooting Sports.

Purpose: turn raw results into useful public and team communication.

Sections:

1. Executive Summary
2. Top Individual Performances
3. Squad Results
4. Podiums and Awards
5. Photo Finishes
6. Personal Records
7. Tentative Team Records
8. Match Records
9. Team MVP Candidates
10. Athlete-by-Athlete Results
11. Data Notes

Highlight rules:

Collapse duplicate leaderboard rows into one story-quality row by athlete, discipline, and score.

Do not generate redundant lines when an athlete appears in Overall, Gender, and Class-based HOA leaderboards for the same performance.

A second-place finish in a TOP 1 board is runner-up or close to win, not a near award miss.

For Nationals-style matches, individual award highlights should use Class-based HOA language. Squad highlights should use Divisional language.

### Suggested Wilco workbook tab order

1. Dashboard
2. Score Audit Summary
3. Registered Athletes
4. Match Scores
5. Rankings
6. Stage Coach View
7. Athlete Stage Matrix
8. Squad Report
9. Squad Members
10. Wilco vs Field
11. Match Records
12. Highlights
13. String Detail
14. Warnings

## Customer 2: SASP framework packages

These packages are generic and should be safe to share with SASP staff without Wilco-specific assumptions.

### Package 3: SASP Match Validation and Score Audit

Customer: SASP staff and match directors.

Purpose: validate score integrity before publication.

Output tabs:

- Score Audit Summary
- Math Validation
- Completeness Checks
- String Anomalies
- Squad Validation
- Hardcopy Reconciliation
- DQ and DNF Review
- Warnings

Severity levels:

- RED
- YELLOW
- ORANGE
- INFO

### Package 4: SASP Reporting and Historical Analytics

Customer: SASP staff and organization.

Purpose: provide neutral match reporting and national historical analytics.

Generic reports:

- Match Summary
- Athlete Results
- Squad Results
- Awards
- Participation Statistics
- Close Finishes

Historical analytics should use meaningful award-scope benchmarks instead of hard-coded Top 1 / Top 3 / Top 5 / Top 10 cohorts.

Core benchmarks, always calculated where data exists:

- Winner Threshold
- Award Threshold, meaning the final awarded place in the correct cohort
- Field Median

Optional benchmarks, based on cohort size:

| Cohort Size | Optional Benchmark |
|---:|---|
| 30 or more competitors | Top 10 Benchmark |
| 75 or more competitors | Top 25 Benchmark |

Compression and competitiveness metrics:

- Winner to Award Gap
- Award to Median Gap
- Winner to Median Gap
- Nationals Difficulty Index
- Improvement Velocity
- Stage Difficulty Index
- Stage Separation Index
- Discipline Trends

### Suggested generic SASP workbook tab order

1. Match Summary
2. Score Audit Summary
3. Math Validation
4. Completeness Checks
5. String Anomalies
6. Athlete Results
7. Squad Results
8. Awards
9. Close Finishes
10. Historical Benchmarks
11. Warnings
