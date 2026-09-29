# 合成数据 API — v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../synthetic-data-api.md](../synthetic-data-api.md)
包 (Package)：`industrial_ai.synthetic` · 相关：[plugin-spec.md](plugin-spec.md)、[ADR-002](../adr/ADR-002-plugin-architecture.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

以下接口已在 `industrial_ai.synthetic` 中**实现 (implemented)**（Phase 4）。

## 1. 生成器接口

```python
class SyntheticDataGenerator(Protocol):
    generator_id: str                    # e.g. "time_series"
    generator_version: str               # semver, e.g. "1.0.0"
    description: str
    parameter_model: type[BaseModel]     # Pydantic model validating `parameters`
    scenario_parameters: frozenset[str]  # scenario parameters this generator can apply

    def generate(
        self,
        schema: DatasetSchema,
        constraints: ConstraintSet,
        scenario: ScenarioSpec | None,
        seed: int,
        size: GenerationSize,
        parameters: BaseModel,           # instance of parameter_model, validated by the engine
        reference: Dataset | DatasetBundle | None = None,
    ) -> GeneratedData: ...              # data + transformation steps + warnings
```

| 参数 | 含义 |
|---|---|
| `schema` | 生成表的目标 schema |
| `constraints` | schema 之外的额外约束（范围、关联关系、求和），见 §3 |
| `scenario` | 其参数用于调整生成过程的场景（例如 `demand_multiplier`）；`None` = 中性 |
| `seed` | 整数种子；随机性的**唯一**来源（`numpy.random.default_rng(seed)`） |
| `size` | 表使用 `GenerationSize(rows=…)`，日序列使用 `(start=…, periods=…)`；未设置的字段由系统推导（例如每个参考行对应一行） |
| `parameters` | 生成器特定参数，由 `parameter_model` 校验 |
| `reference` | 可选的参考数据，用于校准 (calibration)（例如 M5 子集） |

生成器返回的是 `GeneratedData`，而不是数据集：哈希、溯源信息 (provenance) 与校验均由**引擎 (engine)**
计算，因此插件无法产出缺失溯源信息或溯源信息被伪造的数据。

规则：
- 生成器相对于输入是**纯函数 (pure)**：不使用全局随机数生成器 (RNG)，不依赖系统时钟，不访问网络。
- 无效参数抛出 `GeneratorParameterError`；输出违反约束时抛出
  `ConstraintViolationError`（附带 `ValidationReport`）。除非截断规则是一个显式且被记录的参数，
  否则生成器绝不静默地截断 (clip) 或丢弃数据。
- 生成器未应用的场景参数会作为**警告 (warnings)** 列出（记录在结果和溯源信息中），绝不被静默忽略。

## 2. 输出：`SyntheticDataset`

```
SyntheticDataset (a Dataset subtype)
├── data, schema, metadata (source_type = "synthetic"), provenance
├── generation_config   GenerationConfig: generator id/version, schema id/version, constraints,
│                       scenario, seed, size, validated parameters (fully serialisable)
├── validation_report   ValidationReport (always passed; failures raise instead)
├── warnings
└── generator_id / generator_version / random_seed   (properties of generation_config)
```

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
registry = new_generator_registry()                 # core Registry keyed by (generator_id, version)
registry.register(TimeSeriesGenerator())
registry.get("time_series")                          # latest version
describe(registry.get("time_series"))                # GeneratorInfo incl. parameter JSON schema

engine = SyntheticEngine(registry, catalog)          # catalog optional
result = engine.generate(
    GenerationRequest(
        generator_id="time_series",                  # generator_version=None → latest (recorded)
        dataset_id="syn_demand_high", version="1",
        output_schema=SYNTHETIC_DEMAND_SCHEMA,
        constraints=ConstraintSet(...),
        scenario=high_demand,                        # ScenarioSpec or None
        seed=20260927,
        size=GenerationSize(start=date(2016, 1, 1), periods=182),
        parameters={...},
        reference_dataset_id="m5_subset_ca_1_foods_3_top50.sales",   # or pass reference=...
    ),
    register=True,
)
```

引擎的处理流程：解析生成器 → 校验参数 → 解析参考数据（来自参数或目录 (catalog)）→ 调用 `generate` →
构建带溯源信息的数据集（通过哈希固定的输入、组件、已校验的参数、场景、种子、变换、警告）→ 校验
schema 与约束（失败时抛出 `ConstraintViolationError`）→ 在溯源信息中记录校验结果 → 可选地在
目录中注册该数据集。

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

## 6. 初始生成器（v0.1 — 恰好三个，位于 `industrial_ai.synthetic.generators`）

### 6.1 `rule_based` v1.0.0
基于白名单规则词汇逐列构建表（不对任何代码或表达式求值）：`constant`、`sequence`（如 `SUP001`
之类的 id）、`choice`（可选权重）、`uniform`（整数或浮点数）、`linear`（`source × scale + offset`）、
`lookup`（带默认值的映射）以及 `reference_column`（每个参考行对应一个输出行）。规则可以使用先前的列
和参考列。用于：仓库、供应商属性、商品-供应商映射、初始库存、补货策略。

### 6.2 `statistical` v1.0.0
从 `normal`、`lognormal`、`gamma`、`poisson`、`negative_binomial`（均值、离散度 (dispersion)）、
`uniform` 和 `categorical` 分布中对列进行抽样；`copy_from_reference` 按行复制 id 列。可选地通过
Iman–Conover 方法在数值列之间施加**秩相关 (rank correlation)**（边缘分布被精确保留，目标相关性
近似达成；矩阵会被校验是否为合法的相关矩阵）。截断（`clip_min`/`clip_max`）、取整以及整数输出均为
显式参数；被截断的数量记录在溯源信息中。用于：提前期参数、成本比率、可靠性、箱规 (case pack)。

### 6.3 `time_series` v1.0.0
按实体生成的日计数序列：

```
rate_t   = level · season_t · event_t · level_multiplier · shock_t
season_t = max(0, 1 + seasonality_multiplier · (weekly[dow_t] · monthly[month_t] − 1))
y_t ~ NegativeBinomial(mean = rate_t, dispersion = φ / noise_scale²)   or Poisson(rate_t)
noise_scale = 0 → y_t = round(rate_t)
```

- **画像 (Profiles)**：显式的 `profiles`（水平、周度因子 ×7、月度因子 ×12、离散度），或基于参考历史
  （最近 `history_window_days` 天，默认 730）的**逐序列校准 (per-series calibration)**：水平 = 均值，
  周度/月度因子归一化为均值 1，离散度采用矩估计法 (method of moments)（无过度离散时 ≈ 泊松）。每条序列
  **在首次销售之前的前导零会被排除**。v1 不含趋势项，也不含经校准的事件提升 (event uplift)（事件：显式的
  `event_dates` × `event_multiplier`）。
- **场景效应 (Scenario effects)**（通用名称）：`level_multiplier`、`seasonality_multiplier`、`noise_scale`、
  `shock_multiplier`、`shock_start_day`、`shock_duration_days`（自预测区间 (horizon) 起点起算的天数）。
  `scenario_mapping` 将它们映射到场景中的名称，例如 `{"level_multiplier": "demand_multiplier"}`；
  仅应用并报告场景中实际存在的效应。
- 每条序列使用一条独立的随机流（`SeedSequence(seed).spawn`），行先按时间、再按实体排序。输出：
  时间列、实体列、值列，以及可选的 `constant_columns` 和 `scenario_id_column`（例如
  `ops.synthetic_demand`）。
- **已知局限 (Known limitation)**（在真实 M5 子集上观察到，仅为描述性结论）：星期模式与场景比率
  能够被复现，但参考数据中连续的零观测销量日无法被复现，因此合成数据中的零销量日更少。零观测销量可能反映真实的零需求、
  缺货或其他需求截断；M5 没有库存数据，无法区分这些原因。

v0.1 明确**不**包含：GAN、VAE、扩散模型 (diffusion)、基于智能体 (agent-based) 的方法、LLM 生成的数据。

## 7. LLM 辅助生成（P1，预留）

仅允许如下形态：`requirement → LLM → GenerationRequest / scenario proposal (JSON) → schema &
parameter validation → deterministic engine`。LLM 的输出在溯源信息中记录为
`proposal_source="llm"`；LLM 绝不直接写入数据行。
