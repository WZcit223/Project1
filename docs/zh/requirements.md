# 需求 (Requirements) — v0.1

状态：**Gate 0 评审草案** · 语言：中文镜像 · English (authoritative): [../requirements.md](../requirements.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

## 1. 背景

在工业 AI 项目中，主要瓶颈通常不在于模型能力，而在于**数据获取成本、数据稀缺以及结果的可信度**。本项目将**合成数据 (Synthetic Data)** 作为框架的核心能力，并将其与仿真 (Simulation) 和场景分析 (Scenario Analysis) 相结合，为多种工业场景提供可复用的基础能力。

## 2. 目标

构建一个可复用的**工业 AI 应用框架原型 (Industrial AI Application Framework Prototype)**，提供：

```
Data → Synthetic Data → Prediction / Simulation → Scenario / Strategy → Application → Decision Support
```

并通过一个具体的验证场景加以证明：

> **仓储 / 库存 — 库存需求预测与补货仿真 (Inventory Demand Forecasting & Replenishment Simulation)**
> 以历史销售（需求）数据为起点，生成可控的合成需求数据和运营数据，
> 并比较不同补货策略在不同需求/供应场景下的表现。

仓储场景是一个**插件 / 验证案例 (Plugin / Validation Case)**，而不是框架本身。

## 3. 用户

| 角色 | 类型 | 需求 |
|---|---|---|
| 运营经理 (Operations Manager) | 主要用户（演示 UI） | 当前运营状态、库存水平、缺货、补货、需求变化、假设分析 (What-if) 场景、策略结果 |
| 管理层 (Management) | 主要用户（演示 UI） | 整体 KPI、场景对比、成本/服务水平权衡、趋势、决策支持 |
| 数据科学家 / 工程师 / 开发者 | 次要用户（框架使用者） | 通过文档化的 API 扩展新的生成器、模型、策略和场景 |

UI 侧重于运营状态、KPI、场景、假设分析 (What-if Analysis) 和策略对比，**而非**
模型内部细节。

## 4. 功能需求

ID 会在测试和任务待办列表 (Task Backlog) 中被引用。优先级：**P0** 必须，**P1** 应该，**P2** 未来。

### 基础层 (FR-F)

| ID | 需求 | 优先级 |
|---|---|---|
| FR-F1 | 在目录 (Catalog) 中注册数据集，包含 id、版本、模式 (Schema)、元数据、来源和溯源 (Provenance) 信息 | P0 |
| FR-F2 | 按数据集模式校验数据集（类型、必填字段、取值范围、键） | P0 |
| FR-F3 | 通过加载器 (Loader) 接入 CSV/Parquet 表格数据 | P0 |
| FR-F4 | 通过专用适配器将 M5 原始文件转换为规范数据模型 (Canonical Data Model) | P0 |
| FR-F5 | 预览数据集（前 N 行、行数、模式摘要） | P0 |
| FR-F6 | 记录外部来源归属信息（来源、URL、版本、下载日期、许可说明） | P0 |
| FR-F7 | 知识 / 多模态表示 | P2（仅预留接口） |

### 合成数据 (FR-S)

| ID | 需求 | 优先级 |
|---|---|---|
| FR-S1 | 统一的生成器接口：`generate(schema, constraints, scenario, seed, size, parameters) → SyntheticDataset` | P0 |
| FR-S2 | 生成器注册表 (Generator Registry)；按 id + 版本发现；新生成器注册无需修改核心代码 | P0 |
| FR-S3 | 基于规则的生成器 (Rule-based Generator)（库存、供应商、提前期、运营参数） | P0 |
| FR-S4 | 统计生成器 (Statistical Generator)（分布、抽样、相关性） | P0 |
| FR-S5 | 时间序列生成器 (Time-series Generator)（趋势、季节性、噪声、冲击） | P0 |
| FR-S6 | 对生成数据进行约束校验 (Constraint Validation) | P0 |
| FR-S7 | 每个生成的数据集都具备完整的溯源信息 | P0 |
| FR-S8 | 相同输入 + 种子 (Seed) 产生确定性输出 | P0 |
| FR-S9 | LLM 辅助的配置建议（LLM → 配置 → 校验器 → 引擎） | P1 |
| FR-S10 | GAN / VAE / 扩散模型 (Diffusion) / 基于智能体 (Agent-based) 的生成器 | P2 |

### 仿真 / 智能 (FR-M)

| ID | 需求 | 优先级 |
|---|---|---|
| FR-M1 | 统一的仿真接口：`run(dataset, scenario, parameters, constraints) → SimulationResult` | P0 |
| FR-M2 | 仿真插件注册表 | P0 |
| FR-M3 | 需求预测插件：一个基线模型 + 一个机器学习模型 (LightGBM) | P0 |
| FR-M4 | 库存仿真插件（按日、单级、缺货损失销售） | P0 |
| FR-M5 | 补货策略插件：再订货点 (Reorder Point)、安全库存 (Safety Stock)、动态补货 (Dynamic Replenishment) | P0 |
| FR-M6 | 在相同需求和场景下进行策略对比 | P0 |
| FR-M7 | 优化 / 因果模型插件 | P2（仅保证接口兼容） |

### 场景 (FR-C)

| ID | 需求 | 优先级 |
|---|---|---|
| FR-C1 | 场景是显式的、有版本的、经过校验的配置（而非算法） | P0 |
| FR-C2 | 四个初始场景：基线 (Baseline)、高需求 (High Demand)、需求冲击 (Demand Shock)、供应中断 (Supply Disruption) | P0 |
| FR-C3 | 任意场景 × 任意兼容的模型 / 策略组合 | P0 |
| FR-C4 | 通过场景构建器 (Scenario Builder) 创建用户自定义场景（参数须在已校验的范围内） | P0 |

### 应用 / UI (FR-A)

| ID | 需求 | 优先级 |
|---|---|---|
| FR-A1 | 应用 API (Application API)（HTTP/JSON），对外提供数据集、生成器、场景、策略、仿真运行和结果 | P0 |
| FR-A2 | 场景工作流编排 (Scenario Workflow Orchestration)（意图 → 场景 → 数据 → 合成 → 仿真 → 结果） | P0 |
| FR-A3 | UI 页面：概览 (Overview)、数据 (Data)、合成数据 (Synthetic Data)、场景构建器 (Scenario Builder)、仿真 (Simulation)、结果 (Results) | P0 |
| FR-A4 | 轻量级 BI（筛选、分组、聚合、排序、透视、基础统计）— 不可审计 | P1 |
| FR-A5 | 自然语言意图 → 经校验的运行配置（有限智能体） | P1 |
| FR-A6 | 报告：可导出的运行摘要 | P1 |

## 5. 非功能需求

| ID | 需求 |
|---|---|
| NFR-1 可复现性 (Reproducibility) | 相同的源数据 + 生成器版本 + 参数 + 场景 + 种子 → 完全相同的输出；自动化测试验证 |
| NFR-2 可追溯性 (Traceability) | 每个数据集和每次仿真运行都持久化保存溯源信息和运行元数据 |
| NFR-3 可扩展性 (Extensibility) | 新增生成器 / 模型 / 策略 / 场景插件无需修改核心引擎代码 |
| NFR-4 分离性 (Separation) | 核心包从不导入场景代码；UI 从不导入算法模块 |
| NFR-5 简洁性 (Simplicity) | 单进程 Python 应用，SQLite，不使用分布式基础设施 |
| NFR-6 性能 (Performance) | 黄金路径 (Golden Path) 演示运行（子集：约 1 个门店 × 1 个品类 × 前 N 个商品，约 5 年日数据）在笔记本电脑上 < 60 秒完成 |
| NFR-7 可测试性 (Testability) | 单元测试、集成测试、场景测试和黄金路径测试均可基于已提交的合成夹具离线运行 |
| NFR-8 诚实性 (Honesty) | 输出均标注为原型 / 合成；不声称达到第 4 级验证 |
| NFR-9 安全性 (Security) | Git 中不包含密钥或原始外部数据；通过环境变量进行配置 |

## 6. 演示成功标准

用户可在 **5 分钟**内完成：打开仪表盘 → 选择数据集 → 选择生成器 →
生成合成数据 → 选择场景 → 使用两种或以上策略运行仿真 → 对比
结果 → 修改一个假设分析参数并重新运行。

## 7. 交付物 (v0.1.0)

1. 工业 AI 框架原型（数据 → 合成 → 仿真 → 应用，端到端）
2. 合成数据引擎（API、注册表、插件、溯源、可复现性、验证）
3. 仿真引擎（API、插件接口、预测、库存仿真、策略评估）
4. 仓储验证演示（M5 参考数据 + 合成运营数据、场景、假设分析）
5. 技术文档（架构、API、插件、数据模型、场景、验证结果、历史记录、路线图）
6. **算法与数据需求清单**：将每个场景转化为完整生产能力所需的算法和数据
   （维护于 [future-roadmap.md](future-roadmap.md)）。

## 8. 假设（2026-09-27 确认）

| # | 假设 |
|---|---|
| A1 | 库存位置为**单级 (Single-echelon)**：每个 M5 门店被建模为独立的库存点，由一个合成供应商补货。配送中心层级为未来工作。 |
| A2 | 未满足的需求按**缺货损失销售 (Lost Sales)** 处理（不做延期交付），与零售行为一致。 |
| A3 | 演示子集：一个门店 × 一个品类 × 前 N 个商品（默认 CA_1 × FOODS_3，N = 50）；可配置。 |
| A4 | 指标定义见 [data-model.md §6](data-model.md)。 |
| A5 | 原始 M5 数据从不提交；用户使用提供的脚本在本地提取子集。测试使用 M5 格式的合成夹具。 |
| A6 | 英文文档为权威版本 (v1)；中文镜像维护于 `docs/zh/` (v2)。 |
