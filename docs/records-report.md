# Wilco Records Report

## Purpose

The records report creates internal Wilco record candidates, athlete personal
records, match bests, and stage benchmarks from existing local historical
tables. It does not call the SASP API and does not claim official SASP record
status.

Run the complete local history:

```powershell
python -m wilco_as_reporting.cli records-build --team-key wilco --output-dir output
```

Run a match-scoped report:

```powershell
python -m wilco_as_reporting.cli records-build --team-key wilco --output-dir output --match-id 664
```

Match, match-list, match-file, and season filters constrain the report source
scope. The default output directory is `output/records/`.

## Definitions

- A Wilco all-time record candidate is the lowest known valid Wilco score in
  a discipline, discipline/class, or discipline/division scope.
- A team season record is the lowest known valid Wilco score for a discipline
  within a shooting season.
- A personal record is an athlete's lowest known valid score in a discipline.
- PR history starts with the first known valid score and marks a new PR only
  when a later score is lower than the previous PR.
- A match best is the lowest Wilco score within the match's discipline,
  class, or division scope.
- A stage benchmark is a coaching reference. It is not labeled or represented
  as a formal record.

Lower score or time is better. Ties retain every tied athlete and report the
tie count.

## Exclusions and Data Quality

- Blank athlete names and athlete ID `9999` are excluded by default.
- Active mappings in `config/athlete_aliases.csv` merge known spelling
  variants into a canonical coach-facing identity. Original names remain
  available for audit and identity candidate reporting.
- `no_scores` and blank-score rows cannot establish records.
- Partial matches may contribute record candidates, but confidence is reduced.
- Invalid or no-content raw data is absent from the Phase 6A history inputs.
- Use `--include-placeholders` only for data review.

## Personal Record Events and Display Safety

- `initial_pr` is the athlete's first known valid score in a discipline. It
  establishes a baseline but does not represent beating a previous PR.
- `improved_pr` is a later score that is lower than the athlete's prior PR.
- High-confidence records generally have three or more scored entries and no
  obvious partial-match or score-outlier concern.
- Medium-confidence records generally have two scored entries.
- Low-confidence records include one-score baselines, unusually high scores,
  and partial/noisy contexts.
- Low-confidence records remain valid historical rows, but are marked
  display-ineligible by default. A technically valid one-score PR should not
  automatically become a coach, parent, athlete, or social-media celebration.
- `recent_pr_highlights.csv` is the presentation-safe view. Initial PRs remain
  visible as baselines, while only reviewed, reasonable improved PRs are
  marked display-eligible.

## Identity Review

`records_identity_candidates.csv` flags active alias resolutions, matching
athlete IDs with spelling differences, and close names with overlapping
disciplines and seasons. Candidate rows are review aids, not proof. Conflicting
athlete IDs are rejected by the alias loader rather than silently merged.

## Why String and Squad Records Are Excluded

String-level values are scoring components, not the Wilco/SASP record unit
used by this report. Squad results also do not represent individual athlete
records. The records layer therefore creates neither string-record nor
squad-record outputs.

## Limitations

- Results reflect the local history available when the command runs.
- Historical category fields may be blank.
- Identity aliases are curated and should be reviewed when names or athlete
  IDs change.
- Match bests are bests among Wilco entries, not the entire SASP field.
- Stage identity fields are joined from match participation and may be blank
  when historical source rows do not expose them.
- Confidence describes local history coverage, not official certification.
