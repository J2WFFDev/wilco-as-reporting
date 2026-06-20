# Data Sources

## SASP API endpoints

The current project should use API-first data access rather than relying on local JSON folders.

### Slots endpoint

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

### Leaderboard endpoint

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

### Competition list endpoint

```text
https://virtual.sssfonline.com/api/shot/SASP/competitions?type=S&page=1
```

Primary use:

- Discover available matches
- Build historical datasets
- Identify current and prior Nationals match IDs

## Recommended ingestion pattern

1. Fetch API JSON.
2. Save raw snapshots under `data/raw/{match_id}/`.
3. Parse into normalized tables under `data/processed/{match_id}/`.
4. Build reports under `output/{match_id}/`.

## Recommended raw snapshot files

```text
data/raw/664/664_slots.json
data/raw/664/664_leaderboard.json
data/raw/671/671_slots.json
data/raw/671/671_leaderboard.json
```

## Known team/entity ID

Wilco Shooting Sports:

```text
1894
```
