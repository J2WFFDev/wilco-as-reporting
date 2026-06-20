# Match Refresh Strategy

## Purpose

The project should refresh matches selectively instead of requesting every
historical match on every run. Most completed matches become stable, while
active events such as Nationals can change throughout registration and
competition days.

Selective refresh reduces unnecessary API traffic, shortens workflow runtime,
and keeps attention on matches whose data may still change.

## Refresh Modes

### One-Time Bulk Import

A future bulk import will acquire selected historical matches once to create a
baseline dataset. It should use the curated match index, respect forced
exclusions, and avoid repeatedly downloading stable history.

Bulk import is not part of the current implementation.

### Watched Match Refresh

`config/watched_matches.csv` identifies matches that need explicit monitoring.
Active watched matches should be refreshed on every monitoring run, using the
configured schedule preference and refresh priority.

Inactive watched matches remain documented targets for manual or regression
use but should not be refreshed automatically.

### Recent Active Match Refresh

A future refresh process may select matches from the effective match index
when their dates indicate that they are in progress or recently completed.
This catches active events without requiring every match to be listed in the
watchlist.

### On-Demand Single Match Refresh

The existing refresh workflow supports a specific match ID when an operator
needs current raw snapshots immediately. This path is appropriate for
investigation, validation, or a match that is not in the watchlist.

## Watchlist

The tracked watchlist is:

```text
config/watched_matches.csv
```

Its fields describe the match, why it is watched, whether monitoring is
active, whether schedule data should be included by default, its refresh
priority, and operator notes.

The watchlist is configuration, not refresh history. Runtime state belongs in
the refresh manifest.

## Refresh Manifest

The implemented runtime manifest is:

```text
output/state/match_refresh_manifest.csv
```

Current columns:

| Column | Purpose |
| --- | --- |
| `match_id` | SASP match identifier |
| `team_key` | Team profile used for the operational run |
| `match_name` | Current match name |
| `run_timestamp` | Local time when the build ran |
| `snapshot_label` | Operator label such as morning or final |
| `snapshot_path` | Preserved artifact path |
| `raw_slots_hash` | SHA-256 hash of slots JSON |
| `raw_leaderboard_hash` | SHA-256 hash of leaderboard JSON |
| `raw_schedule_hash` | SHA-256 hash of schedule JSON, when available |
| `team_report_hash` | Combined hash of current team report tables |
| `workbook_hash` | Hash of the current team workbook |
| `athlete_count` | Team athletes in the current build |
| `entry_count` | Team discipline entries in the current build |
| `stage_row_count` | Team stage rows in the current build |
| `validation_*_count` | Team ERROR, WARNING, and REVIEW counts |
| `data_status` | `complete`, `partial`, `no_scores`, or other state |
| `notes` | Operator or processing notes |

The manifest should be generated state under `output/`; it should not be
committed as source configuration.

## Candidate Selection Rules

A future refresh selector should:

1. Always refresh watched matches whose `active` value is true.
2. Refresh discovered matches currently in progress.
3. Refresh matches whose end date falls within a recent 7-to-14-day window.
4. Refresh matches marked `force_include` in the curated override file when
   they otherwise meet the run's refresh purpose.
5. Skip matches marked `force_exclude` and matches identified as test,
   practice, demo, sample, copy, or do-not-use data.

The exact recent-match window should be configurable when refresh automation
is implemented.

## Change Detection

For each operational build:

1. Compute a stable hash of the slots, leaderboard, and optional schedule
   JSON.
2. Compare each hash with the previous manifest entry.
3. Append the current hashes and artifact metadata to the runtime manifest.
4. Preserve the full current build in a timestamped snapshot so a later run
   can compare report tables safely without losing the prior state.

Hash comparison should use the saved raw snapshot content. The source JSON
must remain unmodified.

## Nationals Match 671

Match `671`, the 2026 SASP National Championships, is the primary watched
event.

Run the operational refresh with:

```powershell
python -m wilco_as_reporting.cli build-nationals --match-id 671 --output-dir output/671 --team-key wilco --include-schedule --overwrite --snapshot-label manual
```

During Nationals:

- refresh slots and leaderboard repeatedly;
- include schedule data as match metadata by default;
- use high refresh priority;
- update the manifest after each check; and
- preserve timestamped full-build snapshots during event days so changes can
  be audited over time;
- compare the current Wilco results with the latest compatible snapshot; and
- publish a coach-readable daily brief and operations workbook.

The `build-team` command can be run repeatedly for Match `671` to refresh the
full-match and Wilco coaching artifacts. Before leaderboard scoring is
complete, award and comparison tables may be empty while registration,
squads, stage readiness, and validation-review content remain available.

Snapshot folders use:

```text
output/<match_id>/snapshots/<YYYYMMDD_HHMMSS>_<team_key>_<label>/
```

The first run is marked `BASELINE`. Later runs are marked `COMPARED` when the
prior snapshot is compatible. Missing or incompatible prior files produce
`UNAVAILABLE` without crashing. Missing schedule data, incomplete scores, or
temporarily absent rankings also do not fail Match `671`; they are described
in Data Status and Next Actions brief items.

The **Build Nationals Ops Report** workflow supports manual event-day runs.
It restores only the selected match/team snapshot folder and runtime manifest
from an Actions cache, then stores the new state for the next manual run. The
full generated package is still uploaded as a normal downloadable artifact.
No scheduled refresh automation is implemented yet.
