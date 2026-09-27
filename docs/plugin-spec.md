# Plugin Specification — v0.1

Status: **Draft for Gate 0 review** · 中文: [zh/plugin-spec.md](zh/plugin-spec.md)
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

`core.Registry[T]` API: `register(plugin)`, `get(id, version=None)` (latest if omitted),
`list()`, `__contains__`. Duplicate `(id, version)` → `DuplicatePluginError`.

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
class ReplenishmentStrategy(Protocol):
    strategy_id: str
    strategy_version: str
    parameter_model: type[BaseModel]

    def initialise(self, history: ItemHistory, supplier: SupplierInfo,
                   parameters: BaseModel) -> StrategyState: ...

    def decide(self, state: StrategyState, observation: DailyObservation,
               forecast: ForecastView | None) -> OrderDecision: ...
```

`DailyObservation` = date, on_hand, on_order (inventory position), today's demand/fulfilled.
`OrderDecision` = order quantity (int ≥ 0, rounded up to case pack / min order qty) + reason string.
Strategies do **not** mutate inventory; the inventory simulation owns state transitions.

| Strategy | Rule (per item) | Uses forecast |
|---|---|---|
| **A `reorder_point`** (s, Q) | s = μ_hist · L̄ ; when inventory position ≤ s order Q = μ_hist · R (R = review/cycle days, default 14). μ_hist = mean daily demand over the trailing history window, computed once. No safety stock. | No |
| **B `safety_stock`** (s, S) | SS = z · σ_e · √L̄ ; s = μ_f · L̄ + SS ; S = s + μ_f · R ; when position ≤ s order S − position. μ_f = mean forecast daily demand, σ_e = forecast error std on the training window, z from target service level (default 0.95 → 1.645). Parameters fixed at horizon start. | Yes (once) |
| **C `dynamic`** (periodic order-up-to) | Every review day: S_t = Σ forecast over next (L̄ + R) days + z · σ_e,t · √(L̄ + R), σ_e,t = rolling recent forecast error; order max(0, S_t − position). Adapts to scenario changes. | Yes (rolling) |

L̄ = supplier mean lead time (scenario-adjusted as known to the planner). These are deliberately simple
textbook policies; no optimisation.
