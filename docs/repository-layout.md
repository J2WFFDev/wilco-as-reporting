# Repository Layout

The repository uses a small Python source package, tracked CSV configuration,
manual GitHub Actions workflows, current product documentation, and an
ignored generated-output tree.

```text
wilco-as-reporting/
├── .github/
│   └── workflows/              # Active manual operator workflows
├── archive/
│   ├── README.md
│   └── prompts/                # Superseded development prompts
├── config/
│   ├── athlete_aliases.csv
│   ├── match_overrides.csv
│   ├── team_profiles.csv
│   └── watched_matches.csv
├── docs/                       # Current product and operator documentation
├── output/                     # Generated local artifacts; ignored by Git
├── src/
│   └── wilco_as_reporting/
│       ├── api/
│       ├── parsers/
│       ├── reports/
│       ├── validators/
│       ├── workbooks/
│       ├── athlete_aliases.py
│       ├── batch_refresh.py
│       ├── cli.py
│       ├── discovery.py
│       ├── history.py
│       ├── history_insights.py
│       ├── nationals_ops.py
│       ├── nationals_packet.py
│       ├── nationals_readiness.py
│       ├── pipeline.py
│       ├── raw_content.py
│       ├── raw_downloader.py
│       ├── raw_inventory.py
│       ├── records.py
│       ├── refresh_manifest.py
│       └── team_profiles.py
├── .gitignore
├── README.md
└── requirements.txt
```

## Source Responsibilities

- `api/` and `discovery.py`: SASP acquisition and competition catalog.
- `raw_*`: conservative downloading and local useful-content coverage.
- `parsers/`, `validators/`, and `reports/`: normalized match data and
  report-ready tables.
- `workbooks/`: generic, team, and Nationals operations workbooks.
- `history.py` and `history_insights.py`: historical analytics layers.
- `records.py`: Wilco and personal-record reporting.
- `nationals_readiness.py` and `nationals_packet.py`: private coach planning.
- `batch_refresh.py`, `refresh_manifest.py`, and `nationals_ops.py`: bounded
  refresh, state, and event operations.

## Generated Files

Every runtime artifact belongs under `output/`, including JSON snapshots,
CSVs, state manifests, validation findings, and Excel workbooks. These files
are intentionally ignored and must not be committed.

## Archive

The archive contains reference-only historical material. Current production
documentation under `docs/` always takes precedence.

See [repo-inventory.md](repo-inventory.md) for file classifications and active
workflow purposes.
