# Application API — v0.1

Status: **Draft for Gate 0 review** · 中文: [zh/application-api.md](zh/application-api.md) · Related: [ADR-001](adr/ADR-001-api-first.md)

The Application API is the **only** interface the UI (and any future React / mobile / enterprise
client) uses. HTTP + JSON, served by FastAPI under `/api`, OpenAPI schema at `/api/openapi.json`.
Endpoints are finalised in Phase 12; this is the target contract.

## 1. Conventions

- Resource ids are strings; versions are semver strings.
- Long operations (generation, runs) are **synchronous in v0.1** (demo subset runs in < 60 s) but return
  a resource with `status`, so they can become asynchronous later without breaking clients.
- Errors: `{"error": {"code": "SCENARIO_NOT_FOUND", "message": "...", "details": {...}}}` with 4xx/5xx.
- Every run and generated dataset response includes a `provenance` link.
- No authentication in v0.1 (non-goal); the API binds to localhost by default.

## 2. Endpoints

| Method & path | Purpose |
|---|---|
| `GET /health` | `{"status": "ok", "version": "0.1.0"}` |
| `GET /api/scenario-packs` | Installed scenario packs (e.g. `warehouse`) with description |
| `GET /api/datasets` | Catalog list (filter `source_type`, `pack`) |
| `GET /api/datasets/{dataset_id}` | Metadata, schema, provenance |
| `GET /api/datasets/{dataset_id}/preview?limit=50&table=` | First rows + summary stats |
| `GET /api/synthetic/generators` | Registered generators + parameter JSON schema |
| `POST /api/synthetic/generate` | Run a `GenerationRequest` → generated dataset resource |
| `GET /api/scenarios?pack=warehouse` | Scenario list |
| `GET /api/scenarios/{scenario_id}` | Scenario spec + parameter schema |
| `POST /api/scenarios` | Create a user-defined scenario (validated against the pack's parameter schema) |
| `GET /api/models?kind=forecast` | Registered simulation plugins by kind |
| `GET /api/strategies?pack=warehouse` | Registered strategies + parameter schema |
| `POST /api/runs` | Execute an end-to-end scenario run (Golden Path) |
| `GET /api/runs` / `GET /api/runs/{run_id}` | Run list / run detail (status, config, provenance) |
| `GET /api/runs/{run_id}/results` | KPIs per strategy, comparison table |
| `GET /api/runs/{run_id}/timeseries?metric=inventory&strategy=&product=` | Chart series |
| `GET /api/runs/compare?run_ids=a,b` | Cross-run (cross-scenario) KPI comparison |
| `POST /api/intent` *(P1)* | Natural language → proposed `RunRequest` (not executed until confirmed) |

## 3. `POST /api/runs` — request

```json
{
  "pack": "warehouse",
  "reference_dataset_id": "m5_subset_ca1_foods3",
  "scenario_id": "high_demand",
  "scenario_overrides": {"lead_time_delta": 2},
  "demand_source": "synthetic",
  "synthetic": {"generator_id": "time_series", "parameters": {"noise_scale": 1.0}},
  "forecast_model": "lightgbm",
  "strategies": ["reorder_point", "safety_stock", "dynamic"],
  "horizon": {"start_date": "2015-11-01", "days": 182},
  "seed": 20260927
}
```

`demand_source`: `synthetic` (time-series generator calibrated on the reference, scenario applied) or
`reference` (replay of reference demand with scenario multipliers applied deterministically).

## 4. `POST /api/runs` — response (abridged)

```json
{
  "run_id": "run_20260927_0001",
  "status": "succeeded",
  "request": {"...": "echo of the validated request"},
  "scenario": {"scenario_id": "high_demand", "version": "1.0.0", "parameters": {"...": "..."}},
  "results": {
    "strategies": {
      "reorder_point": {"service_level": 0.912, "stockout_rate": 0.061, "inventory_cost": 1834.2, "...": "..."},
      "safety_stock":  {"service_level": 0.957, "...": "..."},
      "dynamic":       {"service_level": 0.968, "...": "..."}
    },
    "forecast": {"model": "lightgbm", "wape": 0.41}
  },
  "labels": ["prototype", "synthetic-data"],
  "provenance_url": "/api/runs/run_20260927_0001#provenance"
}
```

(Numbers are illustrative only.)

## 5. Layering

API routers are thin: validate request models → call `industrial_ai.application` services → map
to response models. No algorithm or data-manipulation logic lives in `api/`. The application layer
calls the Synthetic Data API and Simulation API; it contains orchestration only.
