# 合成数据 API — v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../synthetic-data-api.md](../synthetic-data-api.md)
包 (Package)：`industrial_ai.synthetic` · 相关：[plugin-spec.md](plugin-spec.md)、[ADR-002](../adr/ADR-002-plugin-architecture.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

以下签名为**规范性接口草图 (normative interface sketches)**；确切的类型定义将在 Phase 4 定稿，
届时本文档将同步更新。

## 1. 生成器接口

```python
class SyntheticDataGenerator(Protocol):
    generator_id: str          # e.g. "time_series"
    generator_version: str     # semver, e.g. "1.0.0"
    description: str
    parameter_model: type[BaseModel]   # Pydantic model validating `parameters`

    def generate(
        self,
        schema: DatasetSchema,
        constraints: ConstraintSet,
        scenario: ScenarioSpec | None,
        seed: int,
        size: GenerationSize,
        parameters: Mapping[str, Any],
        reference: Dataset | DatasetBundle | None = None,
    ) -> SyntheticDataset: ...
```

| 参数 | 含义 |
|---|---|
| `schema` | 生成表的目标 schema |
| `constraints` | schema 之外的额外约束（范围、关联关系、求和），见 §3 |
| `scenario` | 其参数用于调整生成过程的场景（例如 `demand_multiplier`）；`None` = 中性 |
| `seed` | 整数种子；随机性的**唯一**来源（`numpy.random.default_rng(seed)`） |
| `size` | 行数、实体数 × 期数，或日期范围，取决于生成器（`GenerationSize`） |
| `parameters` | 生成器特定参数，由 `parameter_model` 校验 |
| `reference` | 可选的参考数据，用于校准 (calibration)（例如 M5 子集） |

规则：
- 生成器相对于输入是**纯函数 (pure)**：不使用全局随机数生成器 (RNG)，不依赖系统时钟，不访问网络。
- 无效参数抛出 `GeneratorParameterError`；输出违反约束时抛出
  `ConstraintViolationError`。除非截断规则是一个显式且被记录的参数，否则生成器绝不静默地截断
  (clip) 或丢弃数据。

## 2. 输出：`SyntheticDataset`

```
SyntheticDataset
├── data               pandas.DataFrame
├── schema             DatasetSchema
├── metadata           DatasetMetadata (source_type = "synthetic")
├── generation_config  {schema_id, constraints, scenario, size, parameters}  (fully serialisable)
├── generator_id
├── generator_version
├── random_seed
└── provenance         ProvenanceRecord
```

`SyntheticDataset` 是 `Dataset` 的子类型，因此所有下游 API 均可接受它。

## 3. 约束

`ConstraintSet` 是一组声明式、可序列化的约束，在生成完成后由
`industrial_ai.foundation.validation` 进行检查：

| 约束 | 示例 |
|---|---|
| `range` | `quantity ≥ 0` |
| `not_null` | `unit_cost` |
| `unique` | 主键 |
| `foreign_key` | `product_supplier.supplier_id ∈ supplier.supplier_id` |
| `relation` | `lead_time_std_days ≤ lead_time_mean_days` |
| `integer` | `quantity` 为整数 |

校验返回一个 `ValidationReport`（通过标志、各约束的结果、违规行数）；
该报告与数据集元数据一同存储。

## 4. 注册表与引擎

```python
registry = GeneratorRegistry()
registry.register(TimeSeriesGenerator())            # key: ("time_series", "1.0.0")
registry.get("time_series")                         # latest version
registry.get("time_series", "1.0.0")                # exact version
registry.list()                                      # [GeneratorInfo(id, version, description, parameter_schema)]

engine = SyntheticEngine(registry, catalog)
result = engine.generate(GenerationRequest(
    generator_id="time_series", generator_version="1.0.0",
    schema_id="retail.sales", scenario_id="high_demand",
    seed=20260927, size=..., parameters={...},
    reference_dataset_id="m5_subset_ca1_foods3",
))
```

引擎的处理流程：解析生成器与 schema → 校验参数 → 调用 `generate` → 校验
约束 → 计算内容哈希 → 写入溯源信息 (provenance) → 在目录 (catalog) 中注册数据集。
重复注册相同的 `(id, version)` 会抛出错误。插件发现 (plugin discovery)：见
[plugin-spec.md](plugin-spec.md)。

UI 与文档中使用的显示 id：`rule_based_v1`、`statistical_v1`、`time_series_v1`。

## 5. 溯源 (Provenance)

每个生成的数据集都会存储一个 `ProvenanceRecord`：

```json
{
  "artifact_id": "syn_demand_7f3a…",
  "artifact_type": "dataset",
  "created_at": "2026-09-27T10:00:00Z",
  "framework_version": "0.1.0",
  "inputs": [{"dataset_id": "m5_subset_ca1_foods3", "version": "1", "content_hash": "sha256:…"}],
  "component": {"id": "time_series", "version": "1.0.0"},
  "parameters": {"noise_scale": 1.0, "calibration": "per_series_negbin"},
  "scenario": {"scenario_id": "high_demand", "version": "1.0.0", "parameters": {"demand_multiplier": 1.3}},
  "seed": 20260927,
  "transformations": [{"step": "calibrate", "details": {...}}, {"step": "apply_scenario", "details": {...}}],
  "output": {"content_hash": "sha256:…", "row_count": 9100},
  "validation": {"passed": true, "report_id": "…"}
}
```

`component` 指明带版本的生产者——此处为生成器；对于导入的数据则为适配器或加载器。它回答了以下链路：*源数据集 → 生成器 → 版本 → 参数 → 场景 → 种子 →
变换 → 生成的数据集*。仅凭溯源记录即可重新执行一次运行（前提是源数据相同），
并通过比较 `content_hash` 验证复现结果。

## 6. 初始生成器（v0.1 — 恰好三个）

### 6.1 `rule_based` v1.0.0
确定性或规则驱动的表：实体列表、属性规则（`unit_cost = price × cost_ratio`）、
基于小型白名单规则词汇（constant、choice、linear、lookup、derived）的逐行表达式。
用于：仓库、供应商属性、商品-供应商映射、初始库存、补货策略。
不对任意代码执行 `eval`。

### 6.2 `statistical` v1.0.0
从参数化分布（正态、对数正态、伽马、泊松、负二项、均匀、分类）中抽样，
并可选地在数值列之间施加高斯 Copula (Gaussian-copula) 相关性。
用于：提前期参数、成本比率、可靠性、箱规 (case pack)。

### 6.3 `time_series` v1.0.0
按实体生成计数型时间序列：

```
λ_t = level · trend_t · weekly[dow_t] · yearly[doy_t] · event_t · scenario_t
y_t ~ NegativeBinomial(mean = λ_t, dispersion = φ)       (Poisson if φ → ∞)
```

- **校准 (Calibration)**（可选，基于 `reference`）：针对每条序列，从参考需求中估计水平、周度模式、年度
  模式、事件提升 (event uplift) 以及离散度 (dispersion)；作为一个变换 (transformation) 记录。
- **场景效应 (Scenario effects)**：`demand_multiplier`、`seasonality_multiplier`（围绕 1 缩放季节性
  振幅）、冲击窗口（在 `[shock_start, shock_start + duration)` 区间内施加 `shock_multiplier`）、噪声尺度。
- 输出符合 `retail.sales` + `scenario_id`（`ops.synthetic_demand`）。

v0.1 明确**不**包含：GAN、VAE、扩散模型 (diffusion)、基于智能体 (agent-based) 的方法、LLM 生成的数据。

## 7. LLM 辅助生成（P1，预留）

仅允许如下形态：`requirement → LLM → GenerationRequest / scenario proposal (JSON) → schema &
parameter validation → deterministic engine`。LLM 的输出在溯源信息中记录为
`proposal_source="llm"`；LLM 绝不直接写入数据行。
