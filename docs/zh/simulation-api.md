# 仿真 API — v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../simulation-api.md](../simulation-api.md)
包 (Package)：`industrial_ai.simulation` · 相关：[plugin-spec.md](plugin-spec.md)、[scenario-spec.md](scenario-spec.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

签名为规范性草图 (normative sketches)，将在 Phase 6 定稿。

## 1. 插件接口

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

`RunContext` 携带 `run_id`、`seed`、仿真期间（`start_date`、`end_date`）、上游结果
（例如库存仿真所使用的预测结果）以及一个日志记录器 (logger)。插件的所有随机性都必须使用
`context.seed`。

## 2. 输出：`SimulationResult`

```
SimulationResult
├── prediction          optional table (e.g. sim.forecast) — forecasts / estimates
├── simulation_result   optional tables (e.g. sim.inventory_ledger, sim.purchase_order)
├── scenario_result     {scenario_id, scenario_version, applied_parameters}
├── metrics             list[Metric(metric_id, value, unit, scope)]
└── metadata            {plugin_id, plugin_version, kind, run_id, seed, parameters,
                         input content hashes, started_at, finished_at, status, warnings}
```

各表均为 `Dataset` 对象（带溯源信息 (provenance)）。`status` 为 `succeeded` 或 `failed`；失败时抛出异常并
被记录；引擎绝不返回虚假的成功结果。

## 3. 引擎与组合

```python
engine = SimulationEngine(registry)
forecast = engine.run("lightgbm", dataset, scenario, params, constraints, ctx)
results = engine.compare(
    plugin_id="inventory_simulation",
    dataset=bundle, scenario=scenario, constraints=constraints, context=ctx.with_upstream(forecast),
    variants={"reorder_point": {...}, "safety_stock": {...}, "dynamic": {...}},
)   # -> ComparisonResult: same data, same scenario, same seed, different strategy parameters
```

组合规则 —— **一个数据集，多种仿真 (one dataset, many simulations)**：任何已注册且其 `required_inputs`
得到满足的插件，都可以在某个数据集上、于其能理解参数的任意场景下运行；未被使用的
场景参数会在 `metadata.warnings` 中报告，绝不静默忽略。

## 4. 初始插件 (v0.1)

| 插件 | 类型 (Kind) | 位置 | 说明 |
|---|---|---|---|
| `moving_average` v1 | forecast | core `simulation/forecasting` | 窗口参数；基线 (baseline) |
| `seasonal_naive` v1 | forecast | core | 周度季节性朴素法 (weekly seasonal naive)（默认基线） |
| `lightgbm` v1 | forecast | core | 跨序列的全局模型；滞后/滚动/日历/价格特征；在仿真期间之前的历史数据上训练一次；每隔 `reforecast_interval_days`（默认 7）进行滚动预测，预测长度为 `forecast_horizon_days`（默认 28），使用截至 *t* 为止观测到的需求 |
| `inventory_simulation` v1 | simulation | warehouse pack | 按日离散时间模型，见 [scenario-spec.md §5](scenario-spec.md) |
| 补货策略 (replenishment strategies) | strategy（供库存仿真使用） | warehouse pack | `reorder_point`、`safety_stock`、`dynamic`；见 [plugin-spec.md §4](plugin-spec.md) |

指令中的名称 `DemandForecastPlugin`、`InventorySimulationPlugin`、`ReplenishmentStrategyPlugin`
分别对应预测插件、`inventory_simulation` 以及策略插件。

预测插件在仿真期间上报告准确度指标：MAE、RMSE、WAPE；M5 WRMSSE 仅可作为参考指标
加入。目标是打通可运行的 Data → Forecast → Simulation 流水线，而非追求预测准确度。

## 5. 预留插件类型（未实现）

| 类型 | 契约说明 |
|---|---|
| `optimization` | 输入预测 + 约束，在 `simulation_result` 中返回决策表（例如订货计划） |
| `causal` | 输入数据集 + 干预规格 (intervention spec)（即一个场景），在 `prediction` 中返回效应估计 |
| 其他领域（维护、生产） | 相同接口，由其他场景包 (scenario pack) 交付 |
