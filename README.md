# Industrial AI Framework (Project1)

A reusable **Industrial AI Application Framework Prototype**:

```
Data → Synthetic Data → Prediction / Simulation → Scenario / Strategy → Application → Decision Support
```

The first validation scenario is **Warehouse / Inventory — Demand Forecasting & Replenishment
Simulation**, built on the M5 Forecasting Accuracy reference dataset plus synthetic operational data.
Warehouse is a *scenario plugin*, not the framework itself.

> Status: **v0.1.0.dev0 — Phases 0–13 implemented** (framework, warehouse pack, Golden Path, Application
> API, demo UI); validation, demo and release follow (Phases 14–16, see [docs/task-backlog.md](docs/task-backlog.md)).
> This is a prototype on synthetic data; see [docs/validation.md](docs/validation.md) for what is and is not
> validated.

## Documentation

| Topic | English (authoritative, v1) | 中文 (v2) |
|---|---|---|
| Requirements | [docs/requirements.md](docs/requirements.md) | [docs/zh/requirements.md](docs/zh/requirements.md) |
| Scope & non-goals | [docs/scope.md](docs/scope.md) | [docs/zh/scope.md](docs/zh/scope.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) | [docs/zh/architecture.md](docs/zh/architecture.md) |
| Data model | [docs/data-model.md](docs/data-model.md) | [docs/zh/data-model.md](docs/zh/data-model.md) |
| Synthetic Data API | [docs/synthetic-data-api.md](docs/synthetic-data-api.md) | [docs/zh/synthetic-data-api.md](docs/zh/synthetic-data-api.md) |
| Simulation API | [docs/simulation-api.md](docs/simulation-api.md) | [docs/zh/simulation-api.md](docs/zh/simulation-api.md) |
| Application API | [docs/application-api.md](docs/application-api.md) | [docs/zh/application-api.md](docs/zh/application-api.md) |
| Plugin spec | [docs/plugin-spec.md](docs/plugin-spec.md) | [docs/zh/plugin-spec.md](docs/zh/plugin-spec.md) |
| Scenario spec | [docs/scenario-spec.md](docs/scenario-spec.md) | [docs/zh/scenario-spec.md](docs/zh/scenario-spec.md) |
| UI spec | [docs/ui-spec.md](docs/ui-spec.md) | [docs/zh/ui-spec.md](docs/zh/ui-spec.md) |
| Validation | [docs/validation.md](docs/validation.md) | [docs/zh/validation.md](docs/zh/validation.md) |
| Task backlog | [docs/task-backlog.md](docs/task-backlog.md) | [docs/zh/task-backlog.md](docs/zh/task-backlog.md) |
| Future roadmap | [docs/future-roadmap.md](docs/future-roadmap.md) | [docs/zh/future-roadmap.md](docs/zh/future-roadmap.md) |
| Development log | [docs/development-log.md](docs/development-log.md) | — |
| ADRs | [docs/adr/](docs/adr/) | — |

Agent / contributor rules: [CLAUDE.md](CLAUDE.md).

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync                      # create the locked environment
uv run pytest                # tests
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy                  # type check
uv run python -m industrial_ai.api   # start the Application API (http://127.0.0.1:8000/health, docs at /api/docs)
uv run python scripts/serve.py       # demo: API + UI in one process, open http://127.0.0.1:8000/ui/
```

The demo UI (`ui/`, package `industrial_ai_ui`) uses only the Application API; runs select reference data by
id (`IAI_REFERENCE_DIRS`, default `m5_subset` → `data/reference/m5_subset/`).

## Data

Raw external data (M5) is **never committed**. Source:
<https://www.kaggle.com/competitions/m5-forecasting-accuracy/data> (Kaggle competition rules apply).
Tests use a small synthetic, M5-shaped fixture (`tests/fixtures/m5_like/`) instead.

To use real M5 data, download the Kaggle files and extract a small subset locally:

```bash
uv run python scripts/make_m5_subset.py --input <folder with the Kaggle CSVs> --download-date YYYY-MM-DD
uv run pytest -m m5_local      # converts and validates data/reference/m5_subset/
```

A small real subset (CA_1 / FOODS_3 / top 50) is committed in `data/reference/m5_subset/` by
owner decision (see its README; Kaggle rules apply, do not redistribute).

Without a checkout of this repository, use the standalone copy (needs only Python ≥ 3.10 and pandas):
`python3 scripts/m5_subset_standalone.py --input <Kaggle folder> --output m5_subset --download-date YYYY-MM-DD`.
It writes the same files.
