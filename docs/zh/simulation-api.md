# 仿真 API — v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../simulation-api.md](../simulation-api.md)
包 (Package)：`industrial_ai.simulation` · 相关：[plugin-spec.md](plugin-spec.md)、[scenario-spec.md](scenario-spec.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

§1–3 中的接口已在 `industrial_ai.simulation` 中**实现**（Phase 6）；§4 中的插件将在 Phase 7–9 中陆续提供。

## 1. 插件接口

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

`RunContext` 携带 `run_id`、`seed`、仿真期间 (horizon)（`start_date`、`end_date`，均为闭区间端点）、
具名的 `upstream` 上游结果（例如 `"forecast"`，通过 `context.require_upstream("forecast")` 读取），
以及一个可选的固定 `created_at`。插件的所有随机性都必须使用 `context.seed`。与生成器 (generator) 一样，
插件只返回原始输出；由**引擎 (engine)** 构建数据集、溯源信息 (provenance) 和元数据 (metadata)。

## 2. 输出：`SimulationResult`

```
SimulationResult
├── prediction          Dataset | None   (e.g. forecasts)
├── simulation_result   {name: Dataset}  (e.g. inventory ledger, purchase orders)
├── scenario_result     {scenario_id, scenario_version, applied_parameters}
├── metrics             tuple[Metric(metric_id, value | None, unit, scope)]
└── metadata            RunMetadata: plugin id/version, kind, run_id, seed, validated parameters,
                        input content hashes (incl. upstream tables), started/finished, status, warnings
```

输出数据集命名为 `<run_id>.<plugin_id>.<table>`，携带溯源信息（输入——包括通过哈希固定的上游表、
插件、参数、场景、种子），并按其模式 (schema) 进行校验。`status` 始终为 `succeeded`：任何失败
（未知插件、缺少输入或上游结果、参数无效、输出无效）都会**抛出异常**；引擎绝不返回失败的或虚假的结果。
指标值在未定义时为 `None`（例如需求为零时的满足率 (fill rate)），绝不使用编造的数字。

## 3. 引擎与组合

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

`compare()` 在相同的数据、场景和种子上，以不同参数运行同一个插件；每个变体 (variant) 的运行 id 为
`<run_id>.<variant>`。组合规则 —— **一个数据集，多种仿真 (one dataset, many simulations)**：任何已注册且其
`required_inputs` 得到满足的插件，都可以在某个数据集上、于任意场景下运行；某次运行未应用的场景参数
会在 `metadata.warnings` 中报告，绝不静默忽略。

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
