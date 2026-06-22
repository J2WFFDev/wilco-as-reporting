# Nationals Coach Packet

## Purpose

The Nationals Coach Packet converts the detailed Match 671 readiness tables
into a concise private meeting packet. It makes no API calls.

```powershell
python -m wilco_as_reporting.cli nationals-packet --team-key wilco --match-id 671 --output-dir output
```

The packet reads existing readiness, records, personal-record, and discipline
history outputs. `--top-priorities` defaults to ten and controls how many
ranked coaching items are retained from the larger readiness watchlist.

## Private and Public-Safe Content

Coach-private outputs may contain watch trends, limited-history context,
confidence focus, and suggested interventions. These are internal planning
notes and are never copied into public-safe shoutout messages.

Public-safe shoutout candidates use only:

- display-eligible improved PRs;
- current PR holders;
- positively phrased near-PR opportunities.

Display-ineligible records, regressions, and private watchlist details are
excluded from shoutouts.

## Priority Ranking

The packet ranks priorities by coach usefulness:

1. new discipline confirmation;
2. limited-history observation;
3. watch-trend stabilization;
4. confidence focus;
5. discipline-level concentration;
6. near-PR and recent-PR reinforcement.

Duplicate athlete/discipline/type rows are removed before applying the
requested priority limit.

## Outputs

The package contains a coach meeting brief, ranked priorities, athlete cards,
public-safe PR shoutout candidates, practice-day focus, match-day watch
points, discipline plans, data-quality notes, and
`wilco_671_nationals_coach_packet.xlsx`.

## Limitations

- The packet is a meeting aid, not a performance prediction.
- Match 671 has entries but no scores.
- Watchlist rows mean coach attention, not failure.
- Public-safe messages should still receive normal coach review before use.
- Private coach notes must not be copied into public or parent-facing content.
