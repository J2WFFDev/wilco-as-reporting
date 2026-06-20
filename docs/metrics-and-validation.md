# Metrics and Validation

## Score validation comes first

Reports should be generated from validated tables. Raw JSON should be parsed once, normalized, validated, and then used for reporting.

## Validation layers

### Level 1: Mathematical Integrity

These should never fail.

- Match total equals sum of four stage scores.
- Stage score equals sum of four counting strings.
- Leaderboard time matches slot-level final score within rounding tolerance.
- Squad score equals sum of four contributing athlete scores.

Suggested severity: RED.

### Level 2: Completeness

- Each athlete / discipline should have four stage scores.
- Each stage should have at least four counting strings.
- Each squad should have four contributing athletes.
- Athlete ID, discipline, class, team, and score should be present where applicable.

Suggested severity: RED or YELLOW depending on context.

### Level 3: Performance Anomaly Review

These are review flags, not automatic errors.

- String below athlete historical norm.
- String below team stage norm.
- Extreme fast string.
- Large spread between fastest and slowest raw strings.
- Stage score far faster than historical baseline.

Suggested severity: ORANGE, YELLOW, or RED based on threshold.

## Fast string review thresholds

Initial thresholds:

| Rule | Severity | Meaning |
|---|---|---|
| String time less than 1.20 seconds | YELLOW | Review recommended |
| String time less than 0.73 seconds | RED | Strong review candidate |
| Faster than athlete stage average by configured threshold | ORANGE | Performance anomaly |

The ORANGE rule should be treated as a coaching review item, not necessarily a scoring error.

## Official scoring metrics

Use `spp*_tot*` fields for official scoring.

A zero in `spp*_tot*` normally indicates the dropped string and should not be treated as a zero-second string.

### Stage score

Stage Score = sum of four counting string totals.

### Scored Avg String

Scored Avg String = Stage Score divided by 4.

Use this for coach-facing views.

## Consistency metrics

Use raw strings for consistency metrics.

Possible metrics:

- Raw 5 Avg String
- String Spread
- Dropped String Delta
- String Standard Deviation

These are analysis metrics, not official scoring metrics.

## Match record metrics

Only these are record-worthy for stage/string records:

- Fastest Individual String by actual stage name
- Fastest Stage Score by actual stage name

Do not include string number in the user-facing record view unless specifically requested.

## Competitive metrics

### Podium Threshold

Score needed to reach the final award position.

Examples:

- 1st place threshold
- 3rd place threshold
- Top 5 threshold
- Top 10 threshold

### Gap to Podium

Athlete Score minus Podium Threshold.

### Gap to Winner

Athlete Score minus Winner Score.

### Compression Index

Top 10 median minus winner score.

Small value means a highly compressed elite field.

### Nationals Difficulty Index

Year-over-year comparison of elite score thresholds by discipline.

### Improvement Velocity

Year-over-year improvement of top competitor groups.

### Stage Difficulty Index

Field median stage score by stage.

### Stage Separation Index

Field median minus top 10 median by stage.

### Clutch Index

Nationals score compared to athlete season average.

Negative value means athlete performed faster than their season average.

### Seconds to Championship

Wilco Top 4 Avg compared to national elite Top 4 Avg or championship threshold.

## Suggested output tables

- score_audit_flags
- hardcopy_reconciliation
- athlete_score_validation
- squad_score_validation
- string_anomalies
- match_scores
- stage_string_scores
- stage_summary
- rankings
- squad_results
- match_records
- wilco_vs_field
- historical_nationals_metrics
