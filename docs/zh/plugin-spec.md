# 插件规格说明（Plugin Specification）— v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../plugin-spec.md](../plugin-spec.md)
相关：[ADR-002](../adr/ADR-002-plugin-architecture.md)，[ADR-004](../adr/ADR-004-scenario-pack-packaging.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

## 1. 插件类型

| 类型 | 接口 | 注册表（Registry） | 示例（v0.1） |
|---|---|---|---|
| 合成数据生成器 | `SyntheticDataGenerator` | `GeneratorRegistry` | rule_based, statistical, time_series |
| 仿真插件 | `SimulationPlugin`（kind：forecast / simulation / strategy_evaluation） | `SimulationRegistry` | seasonal_naive, moving_average, lightgbm, inventory_simulation |
| 补货策略 | `ReplenishmentStrategy`（warehouse 场景包） | `StrategyRegistry`（场景包内部，基于核心 `Registry[T]` 构建） | reorder_point, safety_stock, dynamic |
| 数据集适配器 | `DatasetAdapter` | `AdapterRegistry` | m5 |
| 场景包 | `ScenarioPack` | `ScenarioPackRegistry` | warehouse |

## 2. 通用插件契约

每个插件须：

1. 声明 `id`（snake_case）和 `version`（semver）。注册表的键为 `(id, version)`。
2. 声明一个 Pydantic `parameter_model`；其 JSON schema 通过 API 暴露，使 UI 无需了解插件即可渲染
   表单。
3. 为用户提供一行 `description`（面向运营经理，易于理解），并可为开发者提供可选的 `details`。
4. 所有随机性均来自传入的随机种子（seed）；在给定输入下行为确定。
5. 抛出带类型的错误（`PluginError` 子类）；绝不将部分结果作为成功返回。
6. 具备契约测试（contract test）：注册、参数校验、确定性、输出 schema。
7. 任何导致相同输入产生不同输出的行为变更，都须提升 `version`。

`core.Registry[T]`（实现于 `industrial_ai.core.registry`）：
`Registry(kind, key)`，其中 `key(plugin) → (id, version)` 告诉注册表插件的 id 与版本存放在哪些属性中（例如 `generator_id`、`generator_version`）；`register(plugin)`、
`get(id, version=None)`（省略时取语义化版本最高者）、`list()` 与 `keys()`（按 id、再按版本排序）、`len()`、迭代、`"id" in registry` / `("id", "1.0.0") in registry`。
错误：重复的 `(id, version)` → `DuplicatePluginError`；未知的 id/版本 → `PluginNotFoundError`；版本不是 `MAJOR.MINOR.PATCH` → `InvalidVersionError`（均为 `IndustrialAIError` 的子类）。

## 3. 场景包与发现机制

场景包是一个独立的 Python 包，对外暴露一个 `ScenarioPack` 对象：

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

发现机制（discovery）：使用 Python 入口点（entry point）组 **`industrial_ai.scenario_packs`**，在场景包的
`pyproject.toml` 中声明：

```toml
[project.entry-points."industrial_ai.scenario_packs"]
warehouse = "industrial_ai_warehouse.pack:pack"
```

框架在启动时通过 `importlib.metadata.entry_points` 加载场景包——绝不按名称直接导入
场景包。测试中可显式注册场景包。

用户自行开发的生成器 / 插件遵循相同路径：提供一个在 `industrial_ai.generators` 或
`industrial_ai.simulation_plugins` 组中声明入口点的包。

## 4. 补货策略插件

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

`DailyObservation` = 日期、on_hand（在库量）、on_order（在途量，即库存位置 inventory position）、当日需求/已满足量。
`OrderDecision` = 订货数量（int ≥ 0，向上取整到箱规 / 最小订货量）+ 原因字符串。
策略**不会**修改库存；库存状态转移由库存仿真负责。

| 策略 | 规则（按单品） | 是否使用预测 |
|---|---|---|
| **A `reorder_point`** (s, Q) | s = μ_hist · L̄ ；当库存位置 ≤ s 时订货 Q = μ_hist · R（R = 盘点/周期天数，默认 14）。μ_hist = 回溯历史窗口内的日均需求，仅计算一次。无安全库存。 | 否 |
| **B `safety_stock`** (s, S) | SS = z · σ_e · √L̄ ；s = μ_f · L̄ + SS ；S = s + μ_f · R ；当库存位置 ≤ s 时订货 S − position。μ_f = 预测日均需求，σ_e = 训练窗口上的预测误差标准差，z 由目标服务水平确定（默认 0.95 → 1.645）。参数在预测期起点固定。 | 是（一次） |
| **C `dynamic`**（周期性补货至目标水平，order-up-to） | 每个盘点日：S_t = 未来 (L̄ + R) 天预测值之和 Σ forecast + z · σ_e,t · √(L̄ + R)，σ_e,t = 滚动的近期预测误差；订货 max(0, S_t − position)。能适应场景变化。 | 是（滚动） |

L̄ = 供应商平均提前期（lead time，按计划员所知的场景调整值）。以上均为刻意保持简单的
教科书式策略；不做优化。
