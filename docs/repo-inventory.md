# Repository Inventory

This inventory records the production status of the repository after the
production-readiness cleanup.

Classification values:

- `keep_production`: required by current operation.
- `keep_reference`: useful current context, but not runtime code.
- `archive_legacy`: retained under `archive/` for history only.
- `remove_obsolete`: clearly disposable tracked material.
- `unsure_keep`: retained pending a product decision.

## Production Source Modules

All files under `src/wilco_as_reporting/` are `keep_production`.

| Area | Modules | Purpose |
| --- | --- | --- |
| CLI and orchestration | `cli.py`, `pipeline.py`, `batch_refresh.py` | Registers commands and coordinates builds |
| API and discovery | `api/`, `discovery.py` | SASP requests and competition discovery |
| Raw-data safety | `raw_content.py`, `raw_downloader.py`, `raw_inventory.py` | Download pacing and useful-content inventory |
| Parsing and validation | `parsers/`, `validators/` | Base tables and score reconciliation |
| Reports and workbooks | `reports/`, `workbooks/` | Generic and Wilco match packages |
| Team configuration | `team_profiles.py`, `athlete_aliases.py` | Team and athlete identity resolution |
| Refresh state | `refresh_manifest.py`, `nationals_ops.py` | Change detection and Nationals snapshots |
| Historical layers | `history.py`, `history_insights.py` | Stable history and coach insights |
| Records | `records.py` | Wilco records and personal records |
| Nationals planning | `nationals_readiness.py`, `nationals_packet.py` | Private readiness and coach meeting packet |

No tracked experimental scripts or unused standalone source files were found.

## CLI Commands

All implemented commands are `keep_production`:

1. `discover`
2. `fetch`
3. `download-raw`
4. `raw-status`
5. `backfill`
6. `incremental-refresh`
7. `parse`
8. `validate`
9. `report`
10. `workbook`
11. `build`
12. `team-report`
13. `team-workbook`
14. `build-team`
15. `build-nationals`
16. `history-build`
17. `history-insights`
18. `records-build`
19. `nationals-readiness`
20. `nationals-packet`

`analysis-workbook` is not implemented.

## Configuration Files

All configuration files are `keep_production`:

- `config/team_profiles.csv`
- `config/athlete_aliases.csv`
- `config/match_overrides.csv`
- `config/watched_matches.csv`

## Production Docs

These files are `keep_production` because they document current commands,
data rules, or operator workflows:

- `README.md`
- `docs/data-sources.md`
- `docs/metrics-and-validation.md`
- `docs/report-packages.md`
- `docs/refresh-strategy.md`
- `docs/historical-analytics.md`
- `docs/records-report.md`
- `docs/nationals-readiness.md`
- `docs/nationals-coach-packet.md`
- `docs/repository-layout.md`
- `docs/repo-inventory.md`

## Development and Reference Docs

These files are `keep_reference`:

- `docs/customer-1-wilco.md`: Wilco product intent and report concepts.
- `docs/customer-2-sasp.md`: generic SASP validation/reporting intent.
- `docs/project-philosophy.md`: durable data and reporting principles.

They are not runtime instructions, but they remain useful product context.

## GitHub Actions and Workflows

All eight workflows are `keep_production`. They are manual operator tools and
remain aligned with existing CLI commands.

| Workflow | Purpose |
| --- | --- |
| `discover-matches.yml` | Discover competitions and upload the discovery catalog |
| `fetch-match.yml` | Fetch core raw snapshots for one match |
| `refresh-match.yml` | Refresh one match with optional schedule metadata |
| `build-match-report.yml` | Build the generic single-match report package |
| `build-team-match-report.yml` | Build the Wilco-focused match package |
| `build-nationals-ops.yml` | Refresh, snapshot, and compare Nationals operations |
| `backfill-matches.yml` | Run a bounded historical backfill or dry-run |
| `incremental-refresh.yml` | Refresh watched, active, and recent matches |

No workflow was archived or removed. Historical analytics, records,
readiness, and coach-packet commands remain local-only.

## Archived Items

| File | Classification | Reason |
| --- | --- | --- |
| `archive/prompts/codex-master-prompt.md` | `archive_legacy` | Early development prompt superseded by implemented commands and current docs |

See `archive/README.md` for archive rules.

## Removed Items

No tracked files were classified `remove_obsolete`. No files were deleted.

Ignored Python bytecode and generated `output/` files are local artifacts, not
repository content.

## Candidate Classification

| Candidate | Classification | Decision |
| --- | --- | --- |
| `docs/codex-master-prompt.md` | `archive_legacy` | Moved to `archive/prompts/` |
| Customer product briefs | `keep_reference` | Retain product context |
| `docs/project-philosophy.md` | `keep_reference` | Retain durable principles |
| `docs/repository-layout.md` | `keep_production` | Updated to actual structure |
| All workflow YAML files | `keep_production` | Active manual operator paths |
| Source package | `keep_production` | Every module supports a current command or shared runtime path |
| Generated `output/` files | `remove_obsolete` from Git scope | Remain ignored; never staged or committed |

## Open Cleanup Questions

- Should a future `analysis-workbook` command be added? It is not currently
  implemented and is not documented as an active command.
- Should local-only history/records/Nationals planning commands eventually
  receive manual Actions workflows? They are intentionally local-only today.
- Should the generic Customer 2 SASP concepts become a separate package or
  repository if that product stream becomes active?
