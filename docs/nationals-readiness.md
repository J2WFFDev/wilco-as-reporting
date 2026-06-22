# Nationals Readiness Brief

## Purpose

Phase 6C creates a private, coach-facing readiness brief for the 2026 SASP
National Championships, Match 671. It combines local Nationals entries with
historical performance, personal records, recent PR context, and discipline
trends. It makes no API calls.

```powershell
python -m wilco_as_reporting.cli nationals-readiness --team-key wilco --match-id 671 --output-dir output
```

The command reads local Phase 6A/6B history tables, records tables, and the
parsed Match 671 entry table. The default output folder is
`output/nationals_readiness/`.

## Readiness Levels

- `strong_pr_momentum`: a display-eligible improved PR exists in the selected
  season.
- `near_pr`: the latest score is within two seconds of the internal PR.
- `stable`: useful history exists without a current watch indicator.
- `watch_trend`: current-season history suggests a constructive stability
  focus.
- `limited_history`: one scored match is available.
- `new_or_unscored`: no scored history is available for the entered
  discipline.
- `no_recent_data`: history exists, but recent form should be checked.

## Coach Language

The brief uses supportive internal language such as `watch trend`,
`stabilize`, `confidence focus`, `limited history`, `PR momentum`, and
`needs recent-form check`. It avoids public or harsh labels. The watchlist is
private coaching context.

## Match 671 No-Score Handling

Match 671 currently supplies entry and participation context only. Its blank
scores are never used in personal-record, trend, record, or readiness
calculations. After Nationals results post, rebuild the history, records, and
readiness layers to incorporate the new performance data.

## Outputs

The package includes summary, roster, athlete/discipline readiness, athlete
summary, discipline readiness, PR opportunities, private watchlist, coach
action plan, data-quality notes, and
`wilco_671_nationals_readiness.xlsx`.

## Limitations

- Readiness is a planning aid, not a prediction.
- Internal Wilco PRs are not official SASP records.
- Partial historical matches are context and may reduce confidence.
- Sparse history should be observed before drawing conclusions.
- Athlete aliases are applied from the shared curated alias configuration.
- Class and Division contexts remain separate; this brief does not build
  squad records.
