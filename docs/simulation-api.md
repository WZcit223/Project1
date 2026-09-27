# Simulation API — v0.1

Status: **Approved at Gate 0 (2026-09-27), v0.1 baseline** · 中文: [zh/simulation-api.md](zh/simulation-api.md)
Package: `industrial_ai.simulation` · Related: [plugin-spec.md](plugin-spec.md), [scenario-spec.md](scenario-spec.md)

Interfaces in §1–3 are **implemented** in `industrial_ai.simulation` (Phase 6); §4 plugins follow in Phases 7–9.

## 1. Plugin interface

```python
class SimulationPlugin(Protocol):
    plugin_id: str                    # e.g. "seasonal_naive", "lightgbm", "inventory_simulation"
    plugin_version: str               # semver
    kind: PluginKind                  # forecast | simulation | strategy_evaluation
                                      # reserved: optimization | causal
    description: str
    parameter_model: type[BaseModel]
    required_inputs: tuple[str, ...]  # schema ids the dataset/bundle must contain

    def run(
        self,
        dataset: Dataset | DatasetBundle,
        scenario: ScenarioSpec | None,
        parameters: BaseModel,        # instance of parameter_model, validated by the engine
        constraints: ConstraintSet,
        context: RunContext,
    ) -> PluginOutput: ...            # prediction / tables (schema + DataFrame), metrics,
                                      # warnings, applied_scenario_parameters
```

`RunContext` carries `run_id`, `seed`, the horizon (`start_date`, `end_date`, inclusive), named
`upstream` results (e.g. `"forecast"`, read with `context.require_upstream("forecast")`) and an optional
fixed `created_at`. Plugins must use `context.seed` for all randomness. As with generators, plugins
return raw output; the **engine** builds the datasets, provenance and metadata.

## 2. Output: `SimulationResult`

```
SimulationResult
├── prediction          Dataset | None   (e.g. forecasts)
├── simulation_result   {name: Dataset}  (e.g. inventory ledger, purchase orders)
├── scenario_result     {scenario_id, scenario_version, applied_parameters}
├── metrics             tuple[Metric(metric_id, value | None, unit, scope)]
└── metadata            RunMetadata: plugin id/version, kind, run_id, seed, validated parameters,
                        input content hashes (incl. upstream tables), started/finished, status, warnings
```

Output datasets are named `<run_id>.<plugin_id>.<table>`, carry provenance (inputs incl. upstream
tables pinned by hash, plugin, parameters, scenario, seed) and are validated against their schemas.
`status` is always `succeeded`: any failure (unknown plugin, missing inputs or upstream, invalid
parameters, invalid output) **raises**; the engine never returns a failed or fake result. A metric
value is `None` when undefined (e.g. fill rate with zero demand), never a made-up number.

## 3. Engine and composition

```python
engine = SimulationEngine(registry)          # registry = new_simulation_registry()
forecast = engine.run("lightgbm", bundle, scenario, {...}, ctx)
comparison = engine.compare(
    "inventory_simulation", bundle, scenario,
    variants={"reorder_point": {...}, "safety_stock": {...}, "dynamic": {...}},
    context=ctx.with_upstream("forecast", forecast),
)
comparison.metrics_table()                   # variants × metric ids (pandas DataFrame)
```

`compare()` runs one plugin on the same data, scenario and seed with different parameters; each
variant gets run id `<run_id>.<variant>`. Composition rule — **one dataset, many simulations**: any
registered plugin whose `required_inputs` are satisfied can run on a dataset, under any scenario;
scenario parameters a run does not apply are reported in `metadata.warnings`, never silently ignored.

## 4. Initial plugins (v0.1)

| Plugin | Kind | Location | Notes |
|---|---|---|---|
| `moving_average` v1 | forecast | core `simulation/forecasting` | window parameter; baseline |
| `seasonal_naive` v1 | forecast | core | weekly seasonal naive (default baseline) |
| `lightgbm` v1 | forecast | core | global model over series; lag/rolling/calendar/price features; trained once on history before the horizon; rolling predictions every `reforecast_interval_days` (default 7) for `forecast_horizon_days` (default 28) using demand observed up to *t* |
| `inventory_simulation` v1 | simulation | warehouse pack | daily discrete-time model, see [scenario-spec.md §5](scenario-spec.md#5-inventory-simulation-model) |
| replenishment strategies | strategy (used by inventory simulation) | warehouse pack | `reorder_point`, `safety_stock`, `dynamic`; see [plugin-spec.md §4](plugin-spec.md#4-replenishment-strategy-plugins) |

Instruction names `DemandForecastPlugin`, `InventorySimulationPlugin`, `ReplenishmentStrategyPlugin`
map to the forecast plugins, `inventory_simulation`, and the strategy plugins respectively.

Forecast plugins report accuracy metrics on the horizon: MAE, RMSE, WAPE; M5 WRMSSE may be added as a
reference metric only. The goal is a working Data → Forecast → Simulation pipeline, not forecast accuracy.

## 5. Reserved plugin kinds (not implemented)

| Kind | Contract notes |
|---|---|
| `optimization` | Consumes forecast + constraints, returns decision tables (e.g. order plan) in `simulation_result` |
| `causal` | Consumes dataset + intervention spec (a scenario), returns effect estimates in `prediction` |
| other domains (maintenance, production) | Same interface, delivered by other scenario packs |
