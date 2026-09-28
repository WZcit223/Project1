# Industrial AI Framework (Project1)

A reusable **Industrial AI Application Framework Prototype**:

```
Data → Synthetic Data → Prediction / Simulation → Scenario / Strategy → Application → Decision Support
```

This prototype demonstrates an **Industrial AI Application Framework** through an **Inventory Demand
Forecasting & Replenishment** scenario, using M5 as reference demand data and synthetic operational
data. Keep three things apart:

| | What it is | In this repository |
|---|---|---|
| **Framework** | Reusable, domain-neutral building blocks | `src/industrial_ai/` (never imports a scenario pack) |
| **Scenario** | One inventory case built on the framework's public APIs | `scenarios/warehouse/` (a replaceable plugin) |
| **Real-world validation** | Evidence that results hold for a real warehouse (V4) | **Not performed** |

It is not a warehouse product and has not been shown to improve any real operation; results compare
strategies under identical, controlled simulated conditions.

> Status: **v0.1.0.dev0 — Phases 0–15 implemented** (framework, warehouse pack, Golden Path, Application
> API, demo UI, validation report, demo guide); Phase 16 (v0.1.0 release readiness) in progress, see
> [docs/task-backlog.md](docs/task-backlog.md). What is and is not validated:
> [docs/validation.md](docs/validation.md), [docs/validation-report.md](docs/validation-report.md).

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
| Validation report (generated) | [docs/validation-report.md](docs/validation-report.md) | — |
| **Demo guide** (quick start, demo flow, what is validated) | [docs/demo-guide.md](docs/demo-guide.md) | [docs/zh/demo-guide.md](docs/zh/demo-guide.md) |
| Task backlog | [docs/task-backlog.md](docs/task-backlog.md) | [docs/zh/task-backlog.md](docs/zh/task-backlog.md) |
| Future roadmap | [docs/future-roadmap.md](docs/future-roadmap.md) | [docs/zh/future-roadmap.md](docs/zh/future-roadmap.md) |
| Development log | [docs/development-log.md](docs/development-log.md) | — |
| ADRs | [docs/adr/](docs/adr/) | — |

Agent / contributor rules: [CLAUDE.md](CLAUDE.md).

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+. New here? Start with the
[demo guide](docs/demo-guide.md): quick start, 5–10 minute demo, Golden Path walkthrough and what has
(and has not) been validated.

```bash
uv sync                      # create the locked environment
uv run pytest                # tests
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy                  # type check
uv run python -m industrial_ai.api   # start the Application API (http://127.0.0.1:8000/health, docs at /api/docs)
uv run python scripts/demo.py        # scripted Golden Path via the Application API (~20 s)
uv run python scripts/serve.py       # demo: API + UI in one process, open http://127.0.0.1:8000/ui/
uv run python scripts/validation_report.py   # regenerate docs/validation-report.md (V1–V3; V4 not performed)
```

The demo UI (`ui/`, package `industrial_ai_ui`) uses only the Application API; runs select reference data by
id (`IAI_REFERENCE_DIRS`, default `m5_subset` → `data/reference/m5_subset/`).

## Data

M5 (<https://www.kaggle.com/competitions/m5-forecasting-accuracy/data>, Kaggle competition rules
apply) is store-level retail **sales** — observed sales, not demand, and not warehouse operational
data. It serves as the reference demand/sales environment; all operational data (inventory, suppliers,
lead times, costs, purchase orders) is synthetic.

- **Committed:** only the small owner-approved subset (CA_1 / FOODS_3 / top 50) in
  `data/reference/m5_subset/` (see its README; do not redistribute). Any other raw M5 data stays local
  in git-ignored `data/raw/` and is never committed.
- **Tests:** V1/V2 tests use a small synthetic, M5-shaped fixture (`tests/fixtures/m5_like/`); V3
  reference-data tests (`uv run pytest -m m5_local`) use the committed subset.

To extract a different subset from the full Kaggle files (written to git-ignored `data/raw/m5_subset/`):

```bash
uv run python scripts/make_m5_subset.py --input <folder with the Kaggle CSVs> --download-date YYYY-MM-DD
```

Without a checkout of this repository, use the standalone copy (needs only Python ≥ 3.10 and pandas):
`python3 scripts/m5_subset_standalone.py --input <Kaggle folder> --output m5_subset --download-date YYYY-MM-DD`.
It writes the same files.
