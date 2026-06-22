# Wilco Historical Analytics Foundation

## Purpose

Phase 6A creates a stable, local historical data layer for Wilco Shooting
Sports. It reads existing parsed, ranking, stage, validation, discovery, and
backfill outputs. It does not call the SASP API or download data.

Run a selected set:

```powershell
python -m wilco_as_reporting.cli history-build --team-key wilco --output-dir output --match-ids 578,628,664,665,671,672
```

Run the local core-complete set:

```powershell
python -m wilco_as_reporting.cli history-build --team-key wilco --output-dir output --match-ids-file output/backfill/core_complete_match_ids.txt
```

The command defaults to including partial and no-score matches in
participation context. No-score matches are excluded from performance trends
by default. Use `--no-workbook` to create CSV tables only.

## Outputs

Files are written under `output/history/`:

- `history_source_matches.csv`
- `wilco_match_participation.csv`
- `wilco_athlete_discipline_history.csv`
- `wilco_athlete_overall_history.csv`
- `wilco_discipline_summary.csv`
- `wilco_award_gap_history.csv`
- `wilco_stage_benchmark_history.csv`
- `wilco_data_quality_summary.csv`
- `wilco_history_summary.csv`
- `wilco_history_report.xlsx`, when workbook generation is enabled

## Interpretation Rules

- Lower time is better.
- The shooting season starts September 1 and is labeled `YY-YY Season`.
- Individual award analysis preserves Class scope.
- Squad award context preserves Division scope.
- Overall discipline boards remain comparison context, not official awards.
- Award gaps use the cutoff score from the exact leaderboard when that row is
  available. Missing cutoff information remains blank with a note.
- Match `671` may contribute participation/readiness rows while no scores are
  available, but it does not contribute to performance trends.
- `no_team_entries` means Wilco did not participate; it is not a failure.
- `partial` and `no_scores` are retained as data-quality context.
- Historical validation totals are noisy operational context and are not
  coaching conclusions.

## Limitations

- Athlete IDs are preferred, but athlete names remain the fallback identity.
- Historical source tables do not consistently expose category, role, or
  squad number, so those fields may be blank.
- Squad membership is inferred from generated Wilco squad tables.
- Stage ranks are calculated within Wilco entries for the same match,
  discipline, and stage; they are not field-wide stage rankings.
- Scores from different disciplines are not combined into a single numeric
  overall-performance metric.
