# 架构 (Architecture) — v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../architecture.md](../architecture.md)
相关 ADR：[ADR-001](../adr/ADR-001-api-first.md)、[ADR-002](../adr/ADR-002-plugin-architecture.md)、
[ADR-003](../adr/ADR-003-m5-canonical-adapter.md)、[ADR-004](../adr/ADR-004-scenario-pack-packaging.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

## 1. 分层架构 (Layered Architecture)

```
┌─────────────────────────────────────────────────────┐
│                    UI / UX Layer                    │
│ Dashboard · Data Explorer · Scenario Builder        │
│ Simulation Viewer · KPI / Charts / Tables · Intent  │
└────────────────────────┬────────────────────────────┘
                         │  Application API (HTTP/JSON)
┌────────────────────────▼────────────────────────────┐
│                Application Layer                    │
│ Scenario Workflow · User Intent / Agent [limited]   │
│ Reporting · Decision Support                        │
└────────────────────────┬────────────────────────────┘
                         │  Simulation API
┌────────────────────────▼────────────────────────────┐
│           Simulation / Intelligence Layer           │
│ Forecasting · Simulation · Strategy Evaluation      │
│ Optimization [future] · Causal Modeling [future]    │
└────────────────────────┬────────────────────────────┘
                         │  Dataset API
┌────────────────────────▼────────────────────────────┐
│                 Foundation Layer                    │
│ Data Ingestion · Schema · Catalog · Metadata        │
│ Synthetic Data Engine · Entity Representation       │
│ Knowledge [extension] · Multimodal [extension]      │
└────────────────────────┬────────────────────────────┘
                         │  Synthetic Data API
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
 Rule-based        Statistical        Time-series      (+ user plugins)

──────────────── Cross-cutting infrastructure ────────────────
Configuration · Logging · Versioning · Plugin Registry
Run / Experiment metadata · Provenance · Validation
```

场景插件位于框架**旁侧**，仅通过框架的公开 API 使用框架：

```
                 Industrial AI Framework (src/industrial_ai)
                                │  public APIs + plugin registries
            ┌───────────────────┼────────────────────┐
            ▼                   ▼                    ▼
   Warehouse scenario pack   Maintenance [future]   Energy [future]
   (scenarios/warehouse)
```

## 2. 依赖规则（强制执行）

| 规则 | 执行方式 |
|---|---|
| R1 `industrial_ai` 从不导入任何场景包 (Scenario Pack) | 独立的包 (ADR-004) + 自 Phase 1 起的架构测试 |
| R2 各层只能向下依赖，具体见下表 | 架构测试 `tests/unit/test_architecture.py`（静态导入图检查） |
| R3 UI（templates/static）仅通过 HTTP 与应用 API (Application API) 通信 | UI 中不包含对框架模块的 Python 导入；UI 路由调用 API 客户端 / HTTP |
| R4 插件依赖框架接口，从不依赖彼此的内部实现 | 代码评审 + 测试 |
| R5 除 M5 适配器外，任何模块都不读取原始 M5 文件 | 代码评审 |

`core` 被所有层共享，且不依赖项目内的任何其他部分。

框架内部允许的依赖关系（R2，由 `tests/unit/test_architecture.py` 强制检查）：

| 层 | 可导入 |
|---|---|
| `core` | — |
| `foundation`（含 datasets、catalog、validation、provenance） | `core` |
| `scenario` | `core`、`foundation` |
| `synthetic` | `core`、`foundation`、`scenario` |
| `simulation` | `core`、`foundation`、`scenario` |
| `application` | `core`、`foundation`、`scenario`、`synthetic`、`simulation` |
| `api` | `core`、`application` |

任何模块都可以导入包根 `industrial_ai`（仅包含 `__version__`）以及第三方库。修改此表需同步更新该测试；若改变架构，还需新增 ADR。

## 3. 包 / 模块结构

```
src/industrial_ai/                   # FRAMEWORK CORE — domain-neutral
├── core/          config, logging, errors, ids & versioning, generic Registry[T], plugin discovery
├── foundation/
│   ├── datasets/      Dataset, DatasetSchema, FieldSpec, DatasetRef
│   ├── catalog/       DatasetCatalog (SQLite metadata + artifact storage)
│   ├── ingestion/     tabular loaders (CSV / Parquet), DatasetAdapter protocol
│   ├── transformation/ declarative transforms recorded in provenance
│   ├── provenance/    ProvenanceRecord, lineage helpers
│   ├── entities/      Entity / relationship descriptors (lightweight)
│   └── validation/    schema & constraint validation
├── synthetic/     SyntheticDataGenerator protocol, GeneratorRegistry, SyntheticEngine,
│                  generators/{rule_based, statistical, time_series}, constraints
├── simulation/    SimulationPlugin protocol, SimulationRegistry, SimulationEngine,
│                  forecasting/{baseline, lightgbm}, results, metrics helpers
├── scenario/      ScenarioSpec, ScenarioParameterSchema, ScenarioRegistry (generic)
├── application/   ScenarioPack protocol, workflow runner, run store, reporting, intent [P1]
└── api/           FastAPI app, routers, request/response models (Application API)

scenarios/warehouse/                 # WAREHOUSE SCENARIO PACK — separate package
└── src/industrial_ai_warehouse/
    ├── adapters/m5/     M5 raw → canonical retail-demand dataset (ADR-003)
    ├── schemas/         canonical demand + synthetic operational schemas
    ├── generators/      generator configurations for inventory, supplier, lead time, PO …
    ├── simulation/      InventorySimulationPlugin
    ├── strategies/      ReorderPoint, SafetyStock, DynamicReplenishment
    ├── scenarios/       baseline / high_demand / demand_shock / supply_disruption (YAML)
    ├── metrics.py       KPI definitions (data-model.md §6)
    └── pack.py          WarehouseScenarioPack: registers everything with the framework

ui/                    Jinja2 templates + static (HTMX); served by a thin UI router
scripts/               make_m5_subset.py, make_m5_fixture.py, run_demo.py
```

**为什么预测位于核心而库存位于场景包中：** 时间序列预测 (Time-series Forecasting) 与领域无关
（可复用于能源负荷、传感器信号等）。库存动态和补货策略属于仓储领域逻辑。三个合成数据生成器是通用引擎，
仓储场景包只为它们提供*配置*（模式、规则、分布）。

这一设计细化了指令 §29（该条将 `simulation/inventory` 和 `strategies` 列在核心之下），以
满足更高优先级的规则“仓储特定逻辑不得成为核心架构”。参见 ADR-004。

## 4. 关键抽象 (Key Abstractions)

| 抽象 | 所在层 | 用途 | 规范 |
|---|---|---|---|
| `Dataset` / `DatasetSchema` | foundation | 表格数据 + 模式 + 元数据 + 溯源 | [data-model.md](data-model.md) |
| `DatasetAdapter` | foundation | 外部格式 → 规范数据集 | [data-model.md](data-model.md)，ADR-003 |
| `SyntheticDataGenerator` | synthetic | 可插拔的生成器 | [synthetic-data-api.md](synthetic-data-api.md) |
| `SyntheticDataset` | synthetic | 数据集 + 生成配置 + 溯源 | [synthetic-data-api.md](synthetic-data-api.md) |
| `SimulationPlugin` | simulation | 可插拔的预测 / 仿真 / 策略评估模型 | [simulation-api.md](simulation-api.md) |
| `ReplenishmentStrategy` | warehouse pack | 库存仿真使用的可插拔订货策略 | [plugin-spec.md](plugin-spec.md) |
| `ScenarioSpec` | scenario | 有版本的参数集（而非算法） | [scenario-spec.md](scenario-spec.md) |
| `ScenarioPack` | application | 面向单一领域的模式、生成器、插件、场景、指标和流水线的集合 | [plugin-spec.md](plugin-spec.md) |
| `RunRequest` / `RunResult` | application | 一次可复现的端到端运行 | [application-api.md](application-api.md) |

## 5. 黄金路径 (Golden Path)（运行时流程）

```
User ──► UI ──► Application API  POST /api/runs
                     │
                     ▼
            Workflow runner (application)
                     │  resolves ScenarioPack "warehouse", ScenarioSpec, seed
                     ▼
            Dataset API ── reference dataset (M5 subset → canonical, or fixture)
                     │
          ┌──────────┴───────────┐
          ▼                      ▼
   Reference demand       Synthetic Engine
                           ├─ time_series_v1  → synthetic demand (scenario-adjusted)
                           └─ rule_based_v1 / statistical_v1 → inventory, supplier, lead time, policy
          └──────────┬───────────┘
                     ▼
            Simulation API
             ├─ forecast plugin (seasonal_naive_v1 | lightgbm_v1)
             └─ inventory_simulation_v1 × strategies (reorder_point | safety_stock | dynamic)
                     ▼
            Metrics + ScenarioResult  ──► run store (SQLite + artifacts)
                     ▼
            Application API ──► UI dashboard (KPIs, time series, comparison)
```

每一个跨越层边界的箭头都是一个文档化的接口。每一个产出的制品 (Artifact) 都附带
一条溯源记录，将其关联回输入、生成器/插件版本、场景和种子。

## 6. 横切基础设施 (Cross-cutting Infrastructure)（轻量级）

| 关注点 | v0.1 实现 |
|---|---|
| 配置 | 基于环境变量 / `.env`（`IAI_*`）的 Pydantic settings，场景配置使用 YAML |
| 日志 | 标准库 `logging`，结构化 key=value 格式，每条运行日志均包含 run_id |
| 版本管理 | 包采用语义化版本 (semver)；每个插件都有 `id` + `version`；数据集有版本；模式有版本 |
| 插件注册表 | 通用的进程内 `Registry[T]`，以 `(id, version)` 为键；场景包通过 Python 入口点 (Entry Points)（`industrial_ai.scenario_packs`）发现 |
| 运行 / 实验元数据 | SQLite (SQLModel)：数据集、合成数据生成记录、运行、结果摘要 |
| 制品存储 | 存放于 `data/processed/artifacts/` 下的 Parquet 文件，通过路径 + SHA-256 内容哈希引用 |
| 溯源 | 每个数据集 / 结果都附带存储 `ProvenanceRecord` JSON |
| 验证 | foundation 中的模式 + 约束校验器；场景行为检查在测试中进行 |
| 安全 | 仅在 API 边界；无 IAM（非目标） |

## 7. 技术选型

| 选项 | 决策 |
|---|---|
| 语言 | Python ≥ 3.11 |
| 环境 | uv（`pyproject.toml`、`uv.lock`，场景包使用 workspace） |
| 数据框 (Data Frames) | **pandas**（+ NumPy）。v0.1 不使用 Polars：单一数据框库可保持接口简洁；LightGBM 可直接与 pandas 集成 |
| 列式存储 | 通过 pyarrow 使用 Parquet |
| 模型 / 校验 | Pydantic v2 |
| 持久化 | 基于 SQLite 的 SQLModel |
| API | FastAPI（+ uvicorn） |
| UI | Jinja2 + HTMX，图表使用单一内置 (vendored) JS 图表库（在 Phase 13 中确定） |
| 机器学习 | LightGBM（仅 Phase 7） |
| 开发 | pytest、ruff、mypy (strict) |

依赖仅在需要它们的阶段引入（参见 [task-backlog.md](task-backlog.md)）。

## 8. 预留的扩展点（未实现）

| 未来能力 | 接入位置 |
|---|---|
| GAN / VAE / 扩散模型 / 基于智能体 / LLM 辅助的生成器 | `SyntheticDataGenerator` + 注册表 |
| 因果模型 | `kind="causal"` 的 `SimulationPlugin`；`SimulationResult.prediction` 承载效应估计 |
| 优化 | `kind="optimization"` 的 `SimulationPlugin`，或消费预测结果的策略 |
| 维护 / 能源 / 生产场景 | 在 `scenarios/` 下新建 `ScenarioPack` 包 |
| 知识 / 多模态数据 | 位于 Dataset API 之后的新 foundation 子包 |
| 自然语言智能体 | 应用层 `intent` 模块，生成经校验的 `RunRequest` |
| React / 移动端 UI | 使用同一套应用 API (Application API) |
