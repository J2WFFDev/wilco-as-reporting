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

The implemented `backfill` command acquires a deliberately bounded historical
set to create or refresh the baseline. It uses explicit match selection or the
curated match index, respects exclusions, supports dry-run planning, and can
skip unchanged data.

### Watched Match Refresh

`config/watched_matches.csv` identifies matches that need explicit monitoring.
Active watched matches should be refreshed on every monitoring run, using the
configured schedule preference and refresh priority.

Inactive watched matches remain documented targets for manual or regression
use but should not be refreshed automatically.

### Recent Active Match Refresh

The implemented `incremental-refresh` command can select matches from the
effective match index when their dates indicate that they are active or
recently completed. This catches active events without requiring every match
to be listed in the watchlist.

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
| `last_checked_at` | Most recent fetch/hash check |
| `last_changed_at` | Most recent detected raw-data change |
| `last_success_at` | Most recent successful requested build |
| `last_status` | Success, failure, or unchanged-skip state |
| `last_data_status` | `complete`, `partial`, `no_scores`, or other state |
| `raw_slots_hash` | SHA-256 hash of slots JSON |
| `raw_leaderboard_hash` | SHA-256 hash of leaderboard JSON |
| `raw_schedule_hash` | SHA-256 hash of schedule JSON, when available |
| `team_report_hash` | Combined hash of current team report tables |
| `latest_snapshot_path` | Most recent Nationals snapshot, when created |
| `latest_artifact_name` | Expected workflow artifact name, when relevant |
| `validation_*_count` | ERROR, WARNING, and REVIEW counts from the latest build |
| `notes` | Operator or processing notes |

The manifest should be generated state under `output/`; it should not be
committed as source configuration.

## Candidate Selection Rules

The incremental refresh selector:

1. Always refresh watched matches whose `active` value is true.
2. Refresh discovered matches currently in progress.
3. Refresh matches whose end date falls within a recent 7-to-14-day window.
4. Refresh matches marked `force_include` in the curated override file when
   they otherwise meet the run's refresh purpose.
5. Skip matches marked `force_exclude` and matches identified as test,
   practice, demo, sample, copy, or do-not-use data.

The recent-match window is controlled by `--lookback-days`.

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

## Historical Backfill

The guarded backfill command accepts explicit match IDs or catalog filters:

```powershell
python -m wilco_as_reporting.cli backfill --match-ids 628,664,671 --team-key wilco --output-dir output --include-schedule --dry-run
```

It writes:

```text
output/backfill/backfill_plan.csv
output/backfill/backfill_results.csv
output/backfill/backfill_errors.csv
```

Explicit IDs do not require a competition-list scan. When IDs are omitted,
the command uses the effective discovery index and optional date/post filters.
Force exclusions remain excluded. The recommended first set is Matches
`628`, `664`, and `671`.

## Incremental Refresh

The incremental selector combines:

- active watched matches;
- matches currently between start and end dates;
- matches ending within the lookback window; and
- force-included matches.

Force-excluded and test matches remain excluded. Candidate priority is
watched, active, force-included, then recent. `--max-matches` safely caps the
run and records the cap in candidate notes.

```powershell
python -m wilco_as_reporting.cli incremental-refresh --team-key wilco --output-dir output --lookback-days 14 --include-watched --include-schedule --dry-run
```

Outputs are:

```text
output/incremental/incremental_candidates.csv
output/incremental/incremental_results.csv
output/incremental/incremental_errors.csv
```

## Build Levels and Safety

| Level | Work performed |
| --- | --- |
| `raw` | Fetch raw JSON only |
| `parse` | Fetch and parse base tables |
| `validate` | Parse and create validation tables |
| `report` | Add full-match report CSVs |
| `team` | Add team report CSVs; skip workbooks |
| `nationals` | Run the full Nationals snapshot and workbook pipeline |

Local commands default to dry-run when neither `--dry-run` nor an explicit
`--build-level` is supplied. Manual workflows always default `dry_run` to
true. A non-dry run should specify its build level and a reviewed
`--max-matches` value.

The manifest now stores one current state row per match/team. Every check
updates `last_checked_at` and status. Successful changed data updates
`last_changed_at`; successful processing updates `last_success_at`. Raw,
schedule, and team-report hashes support `SKIPPED_UNCHANGED` results so stable
historical matches do not repeatedly rebuild.

Recommended operating sequence:

1. Dry-run the selected backfill.
2. Backfill a reviewed small match-ID set.
3. Dry-run incremental selection.
4. Refresh watched/recent candidates with a bounded maximum.

Do not run an all-history import until dry-run results are reviewed. Scheduled
automation is still intentionally excluded.
