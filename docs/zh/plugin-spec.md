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

`ItemContext`（在预测期起点已知）：商品、仓库、日需求 `history`（活跃期，排除前导零，取最近
`history_window_days` 天）、计划员所知的 `lead_time_mean_days` / `lead_time_std_days`、
`review_period_days`、`order_cycle_days`、`target_service_level`，以及一个 `ForecastView`（或 `None`）。
`ForecastView.total(day, days)` 对起点 ≤ `day` 的最新一次预测求和；
`ForecastView.recent_errors(day, days)` 返回每个过去日期当时所用预测的误差 — 不做前视（no look-ahead）。
`DailyObservation` = day、date、on_hand（在库量）、on_order（在途量）、inventory_position（库存位置）、当日需求 /
已满足量。策略**不会**修改库存；库存状态转移、取整（箱规、最小订货量）及采购订单均由库存仿真负责。
策略注册在场景包本地的 `StrategyRegistry`（核心 `Registry`）中，并通过仿真参数 `strategy_id` 选择。

已在 `industrial_ai_warehouse.strategies` 中实现（Phase 9）；`builtin_strategies()` 返回一个包含全部三种策略的
注册表。

| 策略 | 规则（按单品） | 是否使用预测 |
|---|---|---|
| **A `reorder_point`** 1.0.0 (s, Q) | s = μ_hist · L̄ ；在盘点日库存位置 ≤ s 时订货 Q = μ_hist · R。μ_hist = 该单品历史窗口（活跃期）内的日均需求，仅计算一次；无历史 → 不订货。无安全库存。 | 否 |
| **B `safety_stock`** 1.0.0 (s, S) | SS = z · σ_e · √L̄ ；s = μ_f · L̄ + SS ；S = s + μ_f · R ；当库存位置 ≤ s 时订货 S − position。在**首次盘点（预测期起点）**时设定，此后固定：μ_f = 未来 ⌈L̄ + R⌉ 天的预测日均需求，σ_e = 预测期起点之前 `error_window_days`（56）天内每日预测误差的标准差。 | 是（一次） |
| **C `dynamic`** 1.0.0（周期性补货至目标水平，order-up-to） | 每 R 天一次（首次盘点为到期日当天或之后的第一个盘点日）：S_t = μ_f,t · (L̄ + R) + z · σ_e,t · √(L̄ + R)，其中 μ_f,t 取自最新一次预测，σ_e,t 取自最近 `error_window_days` 天的误差；订货 max(0, S_t − position)。能适应场景变化。 | 是（滚动） |

通用参数：`cycle_days`（R；默认取该单品的 `order_cycle_days`，14），B 和 C 还有
`service_level`（默认取该单品的 `target_service_level`，0.95 → z = 1.645）和 `error_window_days`。
预测从盘点日的次日开始读取（订单无法满足当天的需求）。当 σ_e 无法估计（过去的误差少于两个：
预测运行需要在预测期之前有一段预热期）或预测未覆盖未来 ⌈L̄ + R⌉ 天时，B 和 C 会抛出
`SimulationInputError`，而不是进行猜测。返回的数量由仿真进行取整（最小订货量 MOQ、箱规）。

**调整频率（有意设计）。** 各策略在调整频率上刻意不同；比较结果展示的是这一差异的影响，而非缺陷：

| 策略 | 角色 | 使用的信息 | 更新 |
|---|---|---|---|
| `reorder_point` | 历史基线 | 预测期之前的需求历史 | 从不（仅计算一次） |
| `safety_stock` | 固定的初始预测 / 基于误差的缓冲 | 预测期起点时已知的预测及预测误差 | 首次盘点后不再更新 |
| `dynamic` | 周期性更新的预测 / 基于误差的目标 | 最新预测及最近 `error_window_days` 天的误差 | 每 R 天 |

**库存位置。** 在每个盘点日，仿真传入一个在当日需求之后、订货之前采集的 `DailyObservation`：`on_hand` = 期末在库量，
`on_order` = 供应商已发货但尚未收到的数量（供应能力削减的部分绝不计入在途），
`inventory_position = on_hand + on_order`。不存在延期交货（back-order，缺货即损失）。三种策略均将其水平（s、S、S_t）
与 `inventory_position` 比较，而绝不仅与 `on_hand` 比较，因此已在途的库存不会被重复订购。订货量为取整前与目标之间的差额。

**冷启动（v0.1 限制）。** 预测期之前没有销售历史的商品在 `reorder_point` 中得到 μ_hist = 0，因此永远不会被补货；
预测类策略依赖预测模型，而对于全零历史，预测模型的预测值也约为 0。新品预测（例如基于类比商品）不在 v0.1 范围内，
已列入 [future-roadmap.md](future-roadmap.md)。

L̄ = 供应商平均提前期（lead time，按计划员所知的场景调整值）。以上均为刻意保持简单的
教科书式策略；不做优化。
