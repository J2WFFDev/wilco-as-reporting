# Metrics and Validation

## Score validation comes first

Reports should be generated from validated tables. Raw JSON should be parsed once, normalized, validated, and then used for reporting.

Run validation after parsing:

```powershell
python -m wilco_as_reporting.cli validate --match-id 664 --output-dir output/664
```

## Validation outputs

Validation writes:

- `validation_summary.csv`: one row per validation check type.
- `validation_findings.csv`: one row per error, warning, review item, or
  informational context finding.
- `match_score_reconciliation.csv`: match final compared with the sum of
  scored stages.
- `stage_score_reconciliation.csv`: four-counting-string structure and scored
  average checks for each stage.
- `squad_score_reconciliation.csv`: squad score compared with the four listed
  athlete scores.

These files are generated under `output/<match_id>/validation/`.

## Severity model

| Severity | Meaning |
| --- | --- |
| `ERROR` | Mathematical mismatch or missing required score data |
| `WARNING` | Incomplete or suspicious data that may be explainable |
| `REVIEW` | Performance anomaly or manual-review item |
| `INFO` | Context that does not invalidate the score |

Fast performance is never an error solely because it is fast. A fastest
non-zero string below 1.20 seconds is a `REVIEW` item. A value below 0.73
seconds is a stronger `REVIEW` item, not an automatic invalidation.

The current parsed stage table preserves stage score, scored average, fastest
non-zero string, and dropped-string count. It does not retain every individual
string value. Stage validation therefore confirms four-string structure and
internal stage arithmetic but does not independently re-sum the original four
counting strings.

The parsed tables also do not retain the raw procedural-penalty field. A
positive match-to-stage difference in a three-second increment is classified
as an informational possible match-level adjustment. Other mathematical
differences remain errors.

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

Competitive benchmarks must be calculated within the correct cohort.

For large matches such as Nationals:

- Individual HOA benchmarks should use Discipline plus Class.
- Gender-context benchmarks should use Discipline plus Class plus Gender where the board exists.
- Squad benchmarks should use Discipline plus Division.
- Overall discipline boards are useful comparison cohorts, but should not be treated as the award cohort.

### Core benchmarks

Always calculate these where data exists:

| Metric | Meaning |
|---|---|
| Winner Threshold | First-place score in the correct cohort |
| Award Threshold | Score of the final awarded place in the correct cohort |
| Field Median | Median score of the full cohort |

### Optional cohort-size benchmarks

Do not hard-code Top 1 / Top 3 / Top 5 / Top 10 as universal metrics. Use optional benchmarks only when the field is large enough.

| Cohort Size | Optional Benchmark |
|---:|---|
| 30 or more competitors | Top 10 Benchmark |
| 75 or more competitors | Top 25 Benchmark |

### Gap to Podium

Athlete Score minus Award Threshold.

### Gap to Winner

Athlete Score minus Winner Threshold.

### Compression Index

Preferred compression metrics:

- Winner to Award Gap
- Award to Median Gap
- Winner to Median Gap

Small values indicate a compressed, competitive field.

### Nationals Difficulty Index

Year-over-year comparison of Winner Threshold, Award Threshold, and Field Median by discipline and award cohort.

### Improvement Velocity

Year-over-year movement in Winner Threshold, Award Threshold, and Field Median.

### Stage Difficulty Index

Field median stage score by stage.

### Stage Separation Index

Field Median minus elite cohort benchmark by stage. The elite cohort should be selected based on cohort size, not hard-coded.

### Clutch Index

Nationals score compared to athlete season average.

Negative value means athlete performed faster than their season average.

### Seconds to Championship

Wilco Top 4 Avg compared to the correct championship benchmark for the cohort.

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
