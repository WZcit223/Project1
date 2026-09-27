# UI Specification — v0.1

Status: **Approved at Gate 0 (2026-09-27), v0.1 baseline** · 中文: [zh/ui-spec.md](zh/ui-spec.md)

## 1. Principles

- **Audience:** Operations Manager and Management. Show operational state, KPIs, scenarios, what-if
  and strategy comparison, not model internals. Technical details sit behind "Details" disclosures.
- **Independence:** the UI calls only the Application API ([application-api.md](application-api.md)).
  It could be replaced by React / mobile without backend changes.
- **Stack:** server-rendered Jinja2 + HTMX; one small chart library, vendored (no Node build).
- **Honesty labels:** every page with results shows a "Prototype · Synthetic data" badge; synthetic
  datasets are visually distinguished from reference data.
- **Language:** English UI in v0.1; labels kept in one message catalog so a Chinese UI can be added.

## 2. Pages

| # | Page | Shows / allows | API used |
|---|---|---|---|
| 1 | **Overview** | KPI tiles for the latest (or selected) run: on-hand inventory value, fill rate, stockout-day rate, ordering / holding / lost-sales / total cost, inventory turnover; demand trend chart; inventory status by strategy | `GET /api/runs`, `/results`, `/timeseries` |
| 2 | **Data** | Reference and synthetic datasets; metadata (source, version, provenance summary); simple field list; data preview table | `GET /api/datasets`, `/preview` |
| 3 | **Synthetic Data** | Select reference dataset, generator, scenario, parameters (form rendered from parameter JSON schema), size, seed → Generate; shows validation report and provenance | `GET /api/synthetic/generators`, `POST /api/synthetic/generate` |
| 4 | **Scenario Builder** | Demand scenario (Normal / High Demand / Demand Shock) and supply scenario (Normal / Disruption) presets; adjust parameters within valid ranges; save as new scenario | `GET/POST /api/scenarios` |
| 5 | **Simulation** | Select dataset, forecast model, strategy(ies), scenario, horizon, seed → Run | `GET /api/models`, `/api/strategies`, `POST /api/runs` |
| 6 | **Results** | KPI comparison table (strategies × KPIs, and scenarios × KPIs across runs); inventory-over-time, demand-over-time and stockout-event charts; tables; what-if: change one parameter and re-run | `GET /api/runs/{id}/results`, `/timeseries`, `/api/runs/compare` |

## 3. Management comparison view (Results)

```
                    Baseline   High Demand   Demand Shock   Supply Disruption
Fill rate              96%        91%            …               …
Stockout-day rate       4%         9%            …               …
Ordering cost         …          …              …               …
Holding cost          …          …              …               …
Lost-sales cost       …          …              …               …
Total cost            …          …              …               …
Purchase orders       …          …              …               …
```
(illustrative)

The key message: *if the environment changes, what happens under each strategy.*

## 4. Lightweight BI (P1)

Filter, group, aggregate, sort, pivot and basic statistics on result tables in the browser or via a
small UI-side helper. **Non-auditable presentation utilities**: official KPIs always come from the
Application API; BI views are labelled "exploratory".

## 5. Demo flow (≤ 5 minutes)

Overview → Scenario Builder (pick High Demand) → Synthetic Data (generate) → Simulation (run three
strategies) → Results (compare) → What-if (change lead time, re-run) → closing statement:
*"The same framework ingests reference data, generates controlled synthetic environments, runs
multiple simulations and supports scenario-based operational decision analysis."*
