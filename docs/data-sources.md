# Data Sources

## SASP API endpoints

The current project should use API-first data access rather than relying on local JSON folders.

## Process overview

The intended data process is:

```text
1. Discover matches
2. Filter usable matches
3. Fetch selected match data
4. Save raw snapshots
5. Parse clean tables
6. Validate scores
7. Generate reports and artifacts
```

The implemented API foundation was delivered in three small pieces:

```text
Phase 2A.1 — API fetch and raw snapshots
Phase 2A.2 — GitHub Actions runner
Phase 2A.3 — Match discovery and match index
```

Parsing, validation, reporting, historical backfill, and selective refresh now
build on this foundation.

## Match discovery endpoint

```text
https://virtual.sssfonline.com/api/shot/SASP/competitions?type=S&page=1
```

Primary use:

- Discover available SASP matches.
- Build a match index.
- Identify State, Regional, National, Local, and Virtual matches.
- Identify current and prior Nationals match IDs.
- Avoid manually hard-coding match IDs when possible.

The discovery process should paginate until no more results are returned.

Important fields to preserve where present:

- `id`
- `name`
- `start_date`
- `end_date`
- `post_raw`
- `post`
- `type`
- `notes`
- stage or taxonomy fields, where present

### Match classification

Use `post_raw` as the primary classification field when available.

Known or likely values:

| post_raw | Likely Meaning |
|---|---|
| `L` | Local |
| `S` | State |
| `R` | Regional |
| `N` | National |
| TBD | Virtual |

Do not assume all values are known yet. Store both `post_raw` and any descriptive field such as `post`.

### Test match filtering

The match discovery layer should filter obvious test or non-production matches.

Initial exclusion rules:

- Exclude names containing `test`.
- Exclude names containing `practice`.
- Exclude names containing `demo`.
- Exclude names containing `sample`.
- Exclude names containing `copy`.
- Exclude names containing `do not use`.

Curated include and exclude decisions are stored in:

```text
config/match_overrides.csv
```

Columns:

```text
match_id,force_include,force_exclude,label,notes
```

Example schedule/test endpoint to avoid as production reporting input:

```text
https://virtual.sssfonline.com/api/shot/sasp-schedule/49
```

## Slots endpoint

```text
https://virtual.sssfonline.com/api/shot/SASP/competitions/{match_id}/slots
```

Example:

```text
https://virtual.sssfonline.com/api/shot/SASP/competitions/664/slots
```

Primary use:

- Team/entity ID
- Hosting team
- Athlete ID
- Athlete name
- Athlete class
- Athlete gender
- Discipline
- Raw strings
- Penalties
- Scored string totals
- Final score
- DQ/DNF flags

Validated paths from prior analysis:

| Data | Path |
|---|---|
| Match ID | `[slot].comp_id` |
| Slot ID | `[slot].id` |
| Slot date | `[slot].date` |
| Slot time | `[slot].time` |
| Team/entity ID | `[slot].ent_id` and `[slot].hosting_team.id` |
| Team name | `[slot].hosting_team.name` |
| Discipline ID | `[slot].disc_id` |
| Discipline description | `[slot].discipline.descr` |
| Athlete ID | `[slot].lineup[].ath_id` |
| Athlete name | `[slot].lineup[].name` |
| Class | `[slot].lineup[].class` |
| Gender | `[slot].lineup[].gender` |
| Raw strings | `spp1_1` through `spp4_5` |
| Penalties | `spp1_pen1` through `spp4_pen5` |
| Scored totals | `spp1_tot1` through `spp4_tot5` |
| Match final | `[slot].lineup[].spp_final` |
| DNF | `[slot].lineup[].dnf_tag` |
| DQ | `[slot].lineup[].dq_tag` |

Important scoring note:

A zero in `spp*_tot*` normally represents the dropped string for that stage. It should not be treated as a zero-second string.

## Leaderboard endpoint

```text
https://virtual.sssfonline.com/api/shot/sasp-leaderboard/{match_id}
```

Example:

```text
https://virtual.sssfonline.com/api/shot/sasp-leaderboard/664
```

Primary use:

- Match name
- Generated timestamp
- Stage names
- Leaderboard rankings
- Award places
- Rank scopes
- Squad results

Validated paths from prior analysis:

| Data | Path |
|---|---|
| Match ID | `id` |
| Match name | `name` |
| Generated timestamp | `generated` |
| Stage 1 name | `stage_one` |
| Stage 2 name | `stage_two` |
| Stage 3 name | `stage_three` |
| Stage 4 name | `stage_four` |
| Disciplines | `disciplines[]` |
| Discipline description | `disciplines[].descr` |
| Leaderboards | `disciplines[].leaderboards[]` |
| Leaderboard type | `leaderboards[].type` |
| Leaderboard name | `leaderboards[].name` |
| Award places | `leaderboards[].places` |
| Rank scope | `leaderboards[].class` |
| Athlete rows | `leaderboards[].data[]` when `type = athlete` |
| Athlete place | `data[].place` |
| Athlete score | `data[].time` |
| Squad rows | `leaderboards[].teams[]` when `type = squad` |
| Squad name | `teams[].squad_name` |
| Squad score | `teams[].score` |
| Squad athletes | `teams[].athletes[]` |

## Schedule endpoint

```text
https://virtual.sssfonline.com/api/shot/sasp-schedule/{match_id}
```

Example:

```text
https://virtual.sssfonline.com/api/shot/sasp-schedule/664
```

Primary use:

- Match schedule metadata
- Bays / locations
- Timing
- Match notes
- Possible stage names or stage notes

Caution:

Match directors are often time-limited, and stage names or taxonomy fields may be incomplete or incorrect. Stage information may be updated in match notes instead of taxonomy fields.

Preferred stage-name priority:

1. Leaderboard stage names when available.
2. Match notes or schedule notes when clearly more accurate.
3. Slots `spp1` through `spp4` structural codes as fallback.

The fetch CLI can include the schedule snapshot when requested:

```powershell
python -m wilco_as_reporting.cli fetch --match-id 671 --output-dir output/671 --overwrite --include-schedule
```

Nationals match `671` should support repeated refreshes while registration,
schedule details, and results are updated during the event. Each refresh
should fetch current slots and leaderboard data and may include the schedule
snapshot.

## Recommended ingestion pattern

1. Fetch competition list pages.
2. Save raw competition list snapshots.
3. Build `match_index.csv`.
4. Apply automatic and manual test-match exclusions.
5. Fetch selected match raw snapshots.
6. Parse into normalized tables.
7. Validate scores.
8. Build report artifacts.

## Recommended raw snapshot files

```text
output/discovery/raw/competitions_page_1.json
output/discovery/tables/match_index.csv
output/discovery/tables/effective_match_index.csv
output/664/raw/664_slots.json
output/664/raw/664_leaderboard.json
output/664/raw/664_schedule.json
output/671/raw/671_slots.json
output/671/raw/671_leaderboard.json
output/671/raw/671_schedule.json
```

## Known team/entity ID

Wilco Shooting Sports:

```text
1894
```

## Discovery command

Run discovery locally or in GitHub Actions:

```powershell
python -m wilco_as_reporting.cli discover --output-dir output/discovery --overwrite
```

`match_index.csv` contains every discovered competition. The effective index
applies automatic name filtering and `config/match_overrides.csv`. A forced
exclusion takes precedence, while a forced inclusion can retain a discovered
match that would otherwise be removed by automatic name filtering.
