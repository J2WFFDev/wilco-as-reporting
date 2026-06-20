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

The recommended runtime manifest is:

```text
output/state/match_refresh_manifest.csv
```

Suggested columns:

| Column | Purpose |
| --- | --- |
| `match_id` | SASP match identifier |
| `match_name` | Current match name |
| `post_raw` | Raw SASP match classification, preserved as received |
| `start_date` | Match start date |
| `end_date` | Match end date |
| `last_checked_at` | Most recent refresh attempt |
| `last_changed_at` | Most recent detected source change |
| `slots_hash` | Hash of the current slots JSON |
| `leaderboard_hash` | Hash of the current leaderboard JSON |
| `schedule_hash` | Hash of the current schedule JSON, when fetched |
| `slots_row_count` | Number of slot records in the current snapshot |
| `leaderboard_generated` | Source-generated leaderboard timestamp |
| `status` | Refresh or match-state summary |
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

For each fetched source:

1. Compute a stable hash of the slots, leaderboard, and optional schedule
   JSON.
2. Compare each hash with the previous manifest entry.
3. If all fetched hashes are unchanged, update `last_checked_at` only.
4. If any hash changed, update `last_checked_at` and `last_changed_at`, store
   the new hashes and metadata, and produce refreshed downstream artifacts.

Hash comparison should use the saved raw snapshot content. The source JSON
must remain unmodified.

## Nationals Match 671

Match `671`, the 2026 SASP National Championships, is the primary watched
event.

During Nationals:

- refresh slots and leaderboard repeatedly;
- include schedule data as match metadata by default;
- use high refresh priority;
- update the manifest after each check; and
- later preserve timestamped raw snapshots during event days so changes can
  be audited over time.

Timestamped event-day snapshots are a future capability. The current refresh
workflow replaces the current raw snapshot when overwrite is enabled.

