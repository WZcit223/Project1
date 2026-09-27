# Plugin Specification — v0.1

Status: **Approved at Gate 0 (2026-09-27), v0.1 baseline** · 中文: [zh/plugin-spec.md](zh/plugin-spec.md)
Related: [ADR-002](adr/ADR-002-plugin-architecture.md), [ADR-004](adr/ADR-004-scenario-pack-packaging.md)

## 1. Plugin types

| Type | Interface | Registry | Examples (v0.1) |
|---|---|---|---|
| Synthetic generator | `SyntheticDataGenerator` | `GeneratorRegistry` | rule_based, statistical, time_series |
| Simulation plugin | `SimulationPlugin` (kind: forecast / simulation / strategy_evaluation) | `SimulationRegistry` | seasonal_naive, moving_average, lightgbm, inventory_simulation |
| Replenishment strategy | `ReplenishmentStrategy` (warehouse pack) | `StrategyRegistry` (pack-local, built on core `Registry[T]`) | reorder_point, safety_stock, dynamic |
| Dataset adapter | `DatasetAdapter` | `AdapterRegistry` | m5 |
| Scenario pack | `ScenarioPack` | `ScenarioPackRegistry` | warehouse |

## 2. Common plugin contract

Every plugin:

1. Declares `id` (snake_case) and `version` (semver). The registry key is `(id, version)`.
2. Declares a Pydantic `parameter_model`; its JSON schema is exposed through the API so UIs can render
   forms without knowing the plugin.
3. Has a one-line `description` for users (Operations-Manager-friendly) and optional `details` for developers.
4. Takes all randomness from the provided seed; is deterministic given inputs.
5. Raises typed errors (`PluginError` subclasses); never returns partial results as success.
6. Has contract tests: registration, parameter validation, determinism, output schema.
7. Bumps `version` on any behaviour change that alters outputs for the same inputs.

`core.Registry[T]` (implemented in `industrial_ai.core.registry`):
`Registry(kind, key)` where `key(plugin) → (id, version)` tells the registry which attributes hold the
id and version (e.g. `generator_id`, `generator_version`); `register(plugin)`,
`get(id, version=None)` (highest semver if omitted), `list()` and `keys()` (ordered by id, then
version), `len()`, iteration, `"id" in registry` / `("id", "1.0.0") in registry`.
Errors: duplicate `(id, version)` → `DuplicatePluginError`; unknown id/version →
`PluginNotFoundError`; version not `MAJOR.MINOR.PATCH` → `InvalidVersionError`
(all subclasses of `IndustrialAIError`).

## 3. Scenario packs and discovery

A scenario pack is a separate Python package exposing a `ScenarioPack` object:

```python
class ScenarioPack(Protocol):
    pack_id: str                      # "warehouse"
    pack_version: str
    title: str                        # "Inventory Demand Forecasting & Replenishment Simulation"
    scenario_parameter_model: type[BaseModel]

    def register(self, registries: FrameworkRegistries) -> None: ...
        # registers schemas, adapters, generator configs, simulation plugins, strategies, scenarios, metrics
    def build_pipeline(self, request: RunRequest) -> Pipeline: ...
        # declarative list of steps the application workflow runner executes
```

Discovery: Python entry points group **`industrial_ai.scenario_packs`**, declared in the pack's
`pyproject.toml`:

```toml
[project.entry-points."industrial_ai.scenario_packs"]
warehouse = "industrial_ai_warehouse.pack:pack"
```

The framework loads packs at startup via `importlib.metadata.entry_points` — it never imports a
pack by name. Tests may register packs explicitly.

User-developed generators / plugins follow the same path: a package with an entry point in group
`industrial_ai.generators` or `industrial_ai.simulation_plugins`.

## 4. Replenishment strategy plugins

```python
class ReplenishmentStrategy(Protocol):            # industrial_ai_warehouse.strategies
    strategy_id: str
    strategy_version: str
    description: str
    parameter_model: type[BaseModel]
    uses_forecast: bool                           # simulation then requires an upstream forecast

    def create_policy(self, item: ItemContext, parameters: BaseModel) -> ItemPolicy: ...

class ItemPolicy(Protocol):
    def order_quantity(self, observation: DailyObservation) -> float: ...   # ≥ 0, before rounding
```

`ItemContext` (known at the horizon start): product, warehouse, daily demand `history` (active period,
leading zeros excluded, last `history_window_days`), planner's `lead_time_mean_days` / `lead_time_std_days`,
`review_period_days`, `order_cycle_days`, `target_service_level` and a `ForecastView` (or `None`).
`ForecastView.total(day, days)` sums the forecast from the latest origin ≤ `day`;
`ForecastView.recent_errors(day, days)` returns errors of the forecasts in use on each past date — no
look-ahead. `DailyObservation` = day, date, on_hand, on_order, inventory_position, today's demand /
fulfilled. Strategies do **not** mutate inventory; the inventory simulation owns state transitions,
rounding (case pack, minimum order quantity) and purchase orders. Strategies are registered in a
pack-local `StrategyRegistry` (core `Registry`) and selected by the simulation parameter `strategy_id`.

Implemented in `industrial_ai_warehouse.strategies` (Phase 9); `builtin_strategies()` returns a registry
with all three.

| Strategy | Rule (per item) | Uses forecast |
|---|---|---|
| **A `reorder_point`** 1.0.0 (s, Q) | s = μ_hist · L̄ ; on a review day with inventory position ≤ s order Q = μ_hist · R. μ_hist = mean daily demand over the item's history window (active period), computed once; no history → no orders. No safety stock. | No |
| **B `safety_stock`** 1.0.0 (s, S) | SS = z · σ_e · √L̄ ; s = μ_f · L̄ + SS ; S = s + μ_f · R ; when position ≤ s order S − position. Set at the **first review (horizon start)** and then fixed: μ_f = mean forecast daily demand over the next ⌈L̄ + R⌉ days, σ_e = std of daily forecast errors in the `error_window_days` (56) before the horizon start. | Yes (once) |
| **C `dynamic`** 1.0.0 (periodic order-up-to) | Every R days (first review on or after the due day): S_t = μ_f,t · (L̄ + R) + z · σ_e,t · √(L̄ + R) with μ_f,t from the latest forecast and σ_e,t from the errors of the last `error_window_days`; order max(0, S_t − position). Adapts to scenario changes. | Yes (rolling) |

Common parameters: `cycle_days` (R; default the item's `order_cycle_days`, 14), and for B and C
`service_level` (default the item's `target_service_level`, 0.95 → z = 1.645) and `error_window_days`.
Forecasts are read from the day after the review (the order cannot serve today's demand). B and C raise
`SimulationInputError` instead of guessing when σ_e cannot be estimated (fewer than two past errors:
the forecast run needs a warm-up before the horizon) or when the forecast does not cover the next
⌈L̄ + R⌉ days. The quantity returned is rounded by the simulation (MOQ, case pack).

L̄ = supplier mean lead time (scenario-adjusted as known to the planner). These are deliberately simple
textbook policies; no optimisation.
