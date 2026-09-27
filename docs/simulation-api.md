# Simulation API — v0.1

Status: **Draft for Gate 0 review** · 中文: [zh/simulation-api.md](zh/simulation-api.md)
Package: `industrial_ai.simulation` · Related: [plugin-spec.md](plugin-spec.md), [scenario-spec.md](scenario-spec.md)

Signatures are normative sketches, finalised in Phase 6.

## 1. Plugin interface

```python
class SimulationPlugin(Protocol):
    plugin_id: str               # e.g. "seasonal_naive", "lightgbm", "inventory_simulation"
    plugin_version: str          # semver
    kind: PluginKind             # "forecast" | "simulation" | "strategy_evaluation"
                                 # reserved: "optimization" | "causal"
    parameter_model: type[BaseModel]
    required_inputs: list[str]   # schema_ids the plugin needs, e.g. ["retail.sales"]

    def run(
        self,
        dataset: Dataset | DatasetBundle,
        scenario: ScenarioSpec,
        parameters: Mapping[str, Any],
        constraints: ConstraintSet,
        context: RunContext,
    ) -> SimulationResult: ...
```

`RunContext` carries `run_id`, `seed`, horizon (`start_date`, `end_date`), upstream results
(e.g. the forecast consumed by the inventory simulation), and a logger. Plugins must use
`context.seed` for all randomness.

## 2. Output: `SimulationResult`

```
SimulationResult
├── prediction          optional table (e.g. sim.forecast) — forecasts / estimates
├── simulation_result   optional tables (e.g. sim.inventory_ledger, sim.purchase_order)
├── scenario_result     {scenario_id, scenario_version, applied_parameters}
├── metrics             list[Metric(metric_id, value, unit, scope)]
└── metadata            {plugin_id, plugin_version, kind, run_id, seed, parameters,
                         input content hashes, started_at, finished_at, status, warnings}
```

Tables are `Dataset` objects (with provenance). `status` is `succeeded` or `failed`; failures raise and
are recorded; the engine never returns a fake success.

## 3. Engine and composition

```python
engine = SimulationEngine(registry)
forecast = engine.run("lightgbm", dataset, scenario, params, constraints, ctx)
results = engine.compare(
    plugin_id="inventory_simulation",
    dataset=bundle, scenario=scenario, constraints=constraints, context=ctx.with_upstream(forecast),
    variants={"reorder_point": {...}, "safety_stock": {...}, "dynamic": {...}},
)   # -> ComparisonResult: same data, same scenario, same seed, different strategy parameters
```

Composition rule — **one dataset, many simulations**: any registered plugin whose `required_inputs`
are satisfied can run on a dataset, under any scenario whose parameters it understands; unused
scenario parameters are reported in `metadata.warnings`, never silently ignored.

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
