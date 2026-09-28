# 技术报告（Technical Report）— v0.1.0

状态：**v0.1.0 候选发布版本（Phase 16）** · English (authoritative): [../technical-report.md](../technical-report.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

面向有 10–15 分钟时间的技术评审者。每一节回答一个问题，并链接到包含细节的规范文档。

> **结论表述。** *本框架在原型级别验证了合成数据生成与场景执行。* 真实运营验证（V4）**尚未**进行。
> 本仓库中没有任何内容表明某个策略、预测或合成数据集对真实仓库是正确的。

## 1. 这是什么？

一个**工业 AI 应用框架原型**：为以下链条提供可复用的基础组件——
*数据 → 合成数据 → 预测 / 仿真 → 场景 / 策略 → 应用 → 决策支持*。

它通过**一个**场景来展示，即*库存需求预测与补货*：使用 M5（沃尔玛门店级零售销量）作为**参考需求数据**，
其余全部使用**合成运营数据**。它不是仓储产品。

| | 是什么 | 位置 |
|---|---|---|
| **框架** | 与领域无关的数据集、溯源、合成数据生成器、预测、仿真引擎、场景注册表、工作流运行器、Application API | `src/industrial_ai/` |
| **场景** | 一个仅基于框架公开 API 构建的库存案例 | `scenarios/warehouse/`（插件包） |
| **UI** | 服务端渲染的演示界面，只调用 Application API | `ui/` |
| **真实世界验证** | 证明结果在真实运营中成立的证据 | **未进行（V4）** |

## 2. 它展示了什么架构？

**分层**（[architecture.md](architecture.md)）：每层只依赖下层；由导入图测试强制保证
（`tests/unit/test_architecture.py`）。

```
Application      workflow runner, run store, ScenarioPack protocol, Application API (FastAPI)
      ▲
Simulation /     SimulationEngine + plugins: forecasting (seasonal naive, moving average, LightGBM);
Intelligence     inventory simulation and strategies come from the scenario pack
      ▲
Synthetic Data   SyntheticEngine + generators: rule_based, statistical, time_series
      ▲
Foundation       Dataset / schema / catalog / validation / provenance / ingestion
      ▲
core             config, logging, errors, versioning, generic plugin Registry
```

**Golden Path（黄金路径）**（一次 `POST /api/runs`，[demo-guide.md §4](demo-guide.md)）：

```
参考数据（M5 子集）→ 规范数据集（schema 检查）→ 合成运营数据 + 场景需求
→ 预测（滚动起点，无前视）→ 库存仿真 × 策略 → 指标
→ 场景对比 → 带溯源的持久化结果
```

由代码强制执行、而不仅是文字声明的设计规则：

- **框架优先** — `industrial_ai` 从不导入场景包（测试 R1）；场景包通过入口点
  `industrial_ai.scenario_packs` 发现（[ADR-004](../adr/ADR-004-scenario-pack-packaging.md)）。
- **场景 ≠ 算法** — 场景是带版本、不可变的参数集（YAML 或用户定义），按场景包的参数模型校验；任何场景都可以
  与任何策略和预测模型组合（[scenario-spec.md](scenario-spec.md)）。
- **API 优先 / UI 边界** — UI → Application API → application → 引擎 → 插件 → 数据集；UI 包不导入任何框架
  模块（AST 测试，[ADR-005](../adr/ADR-005-ui-package.md)）。
- **插件**在注册表中以 `id` + `version` 标识；新增插件无需修改引擎（[plugin-spec.md](plugin-spec.md)）。
- **可复现与溯源** — 相同的参考数据 + 组件版本 + 参数 + 场景（id、版本、覆盖参数）+ 种子 → 相同的指标和
  数据集内容哈希；每个数据集都记录其输入（按内容哈希）、生产者、参数、场景和种子。

## 3. 哪些是框架级，哪些是场景级？

| 关注点 | 框架（可复用） | 库存场景包 |
|---|---|---|
| 数据 | `Dataset`、`DatasetSchema`、`DatasetCatalog`、校验、溯源、CSV/Parquet 导入、`DatasetAdapter` 协议 | M5 适配器、规范零售 schema、运营 schema |
| 合成数据 | `SyntheticDataGenerator` 协议、注册表、引擎、生成器 `rule_based`、`statistical`、`time_series` | 生成器*配置*：仓库、供应商、提前期、成本、初始库存、补货设置；需求校准 |
| 仿真 | `SimulationPlugin` 协议、注册表、引擎；预测插件（领域无关的时间序列） | `inventory_simulation` 插件、KPI 定义、`ReplenishmentStrategy` + `reorder_point`、`safety_stock`、`dynamic` |
| 场景 | `ScenarioSpec`、`ScenarioRegistry`、YAML 加载 | `WarehouseScenarioParameters`；`baseline`、`high_demand`、`demand_shock`、`supply_disruption` |
| 应用 | `ScenarioPack` 协议、`WorkflowRunner`、`RunStore`、`ApplicationService`、Application API | `WarehouseScenarioPack.run`（该领域的流水线） |
| UI | —（独立包，通过 HTTP 通信） | 仅包含显示标签和演示默认值（场景 `baseline`、模型 `seasonal_naive`） |

第二个领域（例如设备维护）将是 `scenarios/` 下的一个新场景包，框架无需修改。v0.1 **尚未**用第二个场景包
演示这一点。

## 4. 实际测试了什么？

来自 [validation-report.md](../validation-report.md)（由 `scripts/validation_report.py` 在提交 `47221e4`、
版本 0.1.0 上生成；该脚本还检查 V1 + V2 + V3 恰好覆盖每个测试一次——379 / 379）：

| 类别 | 问题 | v0.1 证据 | 结果 |
|---|---|---|---|
| **V1** 软件 / 框架正确性 | 模块、插件、接口和指标是否按规范运行？ | 314 个单元与契约测试：注册表、数据集、哈希、溯源、校验、生成器（结构、约束、可复现性）、插件、指标定义、失败模式、架构导入规则 | ✅ |
| **V2** 集成 / Golden Path | 整条链路能否通过运行器、HTTP API 和浏览器 UI 端到端运行？ | 51 个基于合成 M5 结构测试数据（fixture）的测试：Golden Path、API 契约与错误、UI 流程、可复现性、无前视、公平对比（共同随机数） | ✅ |
| **V3** 场景与参考数据验证 | 场景是否按规范表现？框架能否在真实参考数据上正确运行？ | 14 个测试（场景行为；在已提交 M5 子集上的运行）+ 279 项数据检查；在子集上的校准对比、预测回测和 Golden Path——**仅为描述性** | ✅ 原型级别 |
| **V4** 真实运营验证 | 结果对真实仓库是否成立？ | 无 | ⛔ **未进行** |

部分 V3 数据（描述性，不是等价性的通过 / 失败判断）：

| | 数值 |
|---|---|
| 每个序列日的平均需求（参考 vs 合成） | 14.63 vs 18.24（+25%）；有销量的日子 17.48 vs 18.75 |
| 零销量序列日占比 | 16.3%（参考）vs 2.7%（合成） |
| 商品级均值相关系数 | 0.905 |
| 预测回测 WAPE（季节性朴素 / 移动平均 / LightGBM） | 0.443 / 0.459 / 0.413 |
| 子集上的 Golden Path，基线满足率（再订货点 / 安全库存 / 动态） | 84.7% / 86.2% / 93.8%——`scripts/demo.py` 与界面默认运行完全复现 |

## 5. 哪些内容尚未被证明？

- **V4 真实运营验证**——没有真实的库存、采购订单、提前期或成本数据；没有试点。
- 合成运营数据与任何真实企业相似。
- 任何策略在现实中更好。策略对比只在相同、受控的**仿真**条件下成立。
- 预测具有竞争力（模型是基线加一个实用的 ML 模型，并非 M5 竞赛方案）。
- 第二个场景包、多用户运行、安全性、生产部署。

合成数据和参考数据验证（V1–V3）不等于生产验证。

## 6. 已知限制

**数据**
- M5 是门店级**观测零售销量**——是参考数据，不是仓库库存观测；它没有在库或缺货信息。
- **零观测销量 ≠ 已确认缺货**：零销量可能是真实零需求、缺货或其他删失，数据无法区分。观测销量只是需求的
  代理指标。
- 只使用经项目负责人批准的子集 `data/reference/m5_subset/`（CA_1 / FOODS_3 / 前 50）；适用 Kaggle 规则，
  不得再分发。

**合成需求**
- 零销量天数少于参考数据，总体均值更高（在有销量的日子接近）；零需求连续段 / 间歇性需求建模列入路线图。
- 运营数据（成本、提前期、供应商）是合理的占位值，未经任何企业校准；订货成本（每单 20–60 美元）在库存成本
  中占主导。

**库存仿真**
- 单级（每个商品和门店一个库存点）、每个商品一个外部合成供应商、按日步进、缺货即损失（无延期交货或替代）。
- 教科书式策略（再订货点、安全库存、周期性补至目标水平），无优化；各策略的调整频率不同是有意为之
  （[plugin-spec.md §4](plugin-spec.md)）。
- 缺货损失成本按完整售价计算（上限代理），因此在总成本上偏向高库存策略。
- 冷启动：没有销售历史的商品永远不会补货。
- `demand_source = reference`（回放参考需求）未实现。

**应用 / UI**
- 同步运行、单用户、SQLite、无身份认证、英文界面。
- P2 打磨项：图表图例可能与曲线重叠（TASK-P2-LEGEND）；合成数据生成使用 JSON 请求而不是表单
  （TASK-P2-GENFORMS）。

## 7. 下一步是什么？

**v0.1 的范围到此为止。** v0.1.0 是一个可复现、范围清晰的原型；不会再增加新能力。

后续版本的候选项（[future-roadmap.md](future-roadmap.md)），均未开始：

| 时间范围 | 内容 |
|---|---|
| 下一步（P1） | 有限的自然语言意图 → 经校验的运行请求；轻量级 BI；运行报告导出；生成器表单 |
| 之后（P2） | 间歇性需求选项；冷启动处理；优化与因果插件；异步运行；基于真实数据的保真度指标 |
| 需要合作伙伴 | **V4**：真实库存快照、采购订单历史、真实提前期和成本、回测与试点 |
| 长期（P3） | 更多场景包（设备维护、能源）、知识 / 多模态层、企业级部署 |

## 附录 — 五条命令复现

```bash
uv sync
uv run python scripts/demo.py                 # 通过 Application API 运行 Golden Path（约 20 秒）
uv run python scripts/serve.py                # UI：http://127.0.0.1:8000/ui/ — 默认表单即演示配置
uv run pytest                                 # 379 个测试
uv run python scripts/validation_report.py    # 重新生成 docs/validation-report.md
```

演示配置：参考数据 `m5_subset`，场景 `baseline` 1.0.0（以及 `high_demand`），预测模型 `seasonal_naive`，
种子 20260927，91 天预测期。
