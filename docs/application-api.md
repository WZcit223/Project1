# Application API — v0.1

Status: **Approved at Gate 0 (2026-09-27); implemented in Phase 12** · 中文: [zh/application-api.md](zh/application-api.md) · Related: [ADR-001](adr/ADR-001-api-first.md)

The Application API is the **only** interface the UI (and any future React / mobile / enterprise
client) uses. HTTP + JSON, served by FastAPI under `/api`, OpenAPI schema at `/api/openapi.json`,
interactive docs at `/api/docs`. Start locally: `uv run python -m industrial_ai.api`.

## 1. Conventions

- Resource ids are strings; versions are semver strings.
- Long operations (generation, runs) are **synchronous in v0.1** (a demo-subset run takes a few
  seconds) but return a resource with `status`, so they can become asynchronous later without
  breaking clients.
- Errors: `{"error": {"code": "...", "message": "...", "details": {...}}}`:

  | HTTP | code | When |
  |---|---|---|
  | 404 | `NOT_FOUND`, `RUN_NOT_FOUND`, `DATASET_NOT_FOUND` | Unknown pack / scenario / component, run, dataset |
  | 409 | `CONFLICT` | Scenario `(id, version)` or dataset id already exists (specs are immutable) |
  | 422 | `VALIDATION_ERROR` | Request body / query fails the request model (`details.errors`) |
  | 422 | `INVALID_RUN_REQUEST`, `INVALID_SCENARIO`, `INVALID_GENERATION_REQUEST`, `CONSTRAINT_VIOLATION` | Semantically invalid request |
  | 400 | `BAD_REQUEST` | Other framework errors (e.g. unknown result table) |
  | 500 | `RUN_FAILED` | The run's pipeline raised; the run is stored as `failed`, `details.run_id` names it |
  | 500 | `INTERNAL_ERROR` | Unexpected error (logged; no internals in the response) |

- Provenance: a run lists `inputs` and `outputs` as `(dataset_id, version, content_hash)`;
  `GET /api/datasets/{dataset_id}` returns each dataset's full provenance record.
- Reference data is selected by a **reference dataset identifier** `reference_id` (e.g. `m5_subset`;
  pattern `^[A-Za-z0-9][A-Za-z0-9_.-]*$`). It names a reference dataset configured on the server
  (`IAI_REFERENCE_DIRS`); it is **not** a file path. Path-like values are rejected (422), and the
  server-side location is never returned (run records show only `request.reference_id`).
- **Re-run semantics:** a stored run is reproduced by posting its `pack`, `reference_id`, `scenario_id`,
  `scenario.version` (pin it — omitting the version selects the latest), `seed`, `horizon_days`,
  `options` and `scenario_overrides`; a what-if adds or changes one override. Same inputs → same
  metrics (tested).
- No authentication in v0.1 (non-goal); the API binds to localhost by default.

## 2. Endpoints (implemented)

| Method & path | Purpose |
|---|---|
| `GET /health` | `{"status": "ok", "version": "0.1.0"}` |
| `GET /api/scenario-packs` | Installed scenario packs with description and scenario ids |
| `GET /api/references` | Configured reference ids and whether their data is available |
| `GET /api/datasets?source_type=` | Catalog list |
| `GET /api/datasets/{dataset_id}?version=` | Summary, schema, metadata, provenance |
| `GET /api/datasets/{dataset_id}/preview?limit=50&version=` | First rows + per-column statistics |
| `GET /api/synthetic/generators` | Registered generators + parameter JSON schema |
| `POST /api/synthetic/generate` | Run a `GenerationRequest` → registered dataset summary (201) |
| `GET /api/scenarios?pack=warehouse` | Scenario list (pack scenarios + user scenarios) |
| `GET /api/scenarios/{scenario_id}?pack=&version=` | Spec, effective parameters, parameter schema |
| `POST /api/scenarios` | Create a user-defined scenario (`source: user`), validated against the pack's parameter model (201) |
| `GET /api/models?pack=warehouse&kind=forecast` | Simulation plugins of the pack (kinds `forecast`, `simulation`) |
| `GET /api/strategies?pack=warehouse` | Strategies + parameter schema |
| `POST /api/runs` | Execute an end-to-end scenario run (Golden Path) → run record (201) |
| `GET /api/runs` / `GET /api/runs/{run_id}` | Run list (newest first) / run record |
| `GET /api/runs/{run_id}/results` | KPIs per strategy (variant), supporting metrics, labels |
| `GET /api/runs/{run_id}/timeseries?variant=&table=&column=&filter=key:value` | Daily series of a result column, summed over matching entities |
| `GET /api/runs/compare?run_ids=a,b` | Cross-run (cross-scenario) KPI rows: run × variant |
| `POST /api/intent` *(P1, not implemented)* | Natural language → proposed run request (not executed until confirmed) |

Time series example: `variant=dynamic&table=inventory_ledger&column=closing_on_hand&filter=product_id:FOODS_3_090`.

## 3. `POST /api/runs` — request

```json
{
  "pack": "warehouse",
  "reference_id": "m5_subset",
  "scenario_id": "high_demand",
  "scenario_version": null,
  "scenario_overrides": {"lead_time_delta": 2},
  "seed": 20260927,
  "horizon_days": 91,
  "options": {
    "forecast_model": "lightgbm",
    "strategies": ["reorder_point", "safety_stock", "dynamic"],
    "warm_up_days": 56,
    "forecast_horizon_days": 56
  }
}
```

- The framework fields are generic; `options` are validated by the pack (`warehouse`:
  `forecast_model` ∈ `seasonal_naive` | `moving_average` | `lightgbm`, `strategies`,
  `warm_up_days`, `forecast_horizon_days`).
- `scenario_overrides` are validated against the pack's scenario parameter model and recorded.
- The horizon starts the day after the last observed sale of the reference data (a free start date is
  not supported in v0.1).
- Demand is always synthetic (time-series generator calibrated on the reference, scenario applied).
  Replaying reference demand (`demand_source = reference` in the Gate 0 draft) is **NOT IMPLEMENTED**.

Internally the service maps this body onto the application layer's `RunRequest` (same fields, with
`reference` = the configured directory of `reference_id`).

## 4. `POST /api/runs` — response (abridged)

```json
{
  "run_id": "run_20260928_101500_1a2b3c4d",
  "status": "succeeded",
  "pack": "warehouse",
  "pack_version": "0.1.0",
  "request": {"...": "validated request"},
  "scenario": {"scenario_id": "high_demand", "version": "1.0.0", "parameters": {"...": "..."}, "source": "pack"},
  "scenario_overrides": {"lead_time_delta": 2},
  "labels": ["prototype", "synthetic-data"],
  "variant_metrics": {
    "reorder_point": {"fill_rate": 0.912, "stockout_day_rate": 0.061, "ordering_cost": 1650.0, "holding_cost": 184.2, "lost_sales_cost": 1286.3, "total_cost": 3120.5, "...": "..."},
    "safety_stock":  {"fill_rate": 0.957, "...": "..."},
    "dynamic":       {"fill_rate": 0.968, "...": "..."}
  },
  "supporting_metrics": {"forecast": {"wape": 0.41, "...": "..."}},
  "inputs":  {"synthetic_demand": {"dataset_id": "...", "version": "1", "content_hash": "sha256:..."}, "...": "..."},
  "outputs": {"dynamic.inventory_ledger": {"dataset_id": "...", "version": "1", "content_hash": "sha256:..."}, "...": "..."},
  "created_at": "...", "finished_at": "...", "error": null
}
```

(Numbers are illustrative only.)

## 5. Layering

API routers are thin: validate request models → call `industrial_ai.application.ApplicationService`
→ return its read models. No algorithm or data-manipulation logic lives in `api/`, and `api/` imports
only `core` and `application` (architecture test). The application layer calls the Synthetic Data API
and Simulation API; it contains orchestration only.
