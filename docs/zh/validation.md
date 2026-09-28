# 验证规范 — v0.1

状态：**已于 Gate 0 批准（2026-09-27）；于 Phase 14 重新表述验证类别（2026-09-28）** · English (authoritative): [../validation.md](../validation.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

> v0.1 验证的是**框架**本身，而非合成数据在真实世界中的准确性。
> 允许的表述：*"The framework validates synthetic data generation and scenario execution at the prototype level."*（"该框架在原型层面验证了合成数据生成与场景执行。"）

## 1. 验证类别

v0.1 严格区分四个类别。每项结果只归入其中一个类别进行报告
（`docs/validation-report.md`，由 `scripts/validation_report.py` 生成）。

| 类别 | 问题 | v0.1 中的证据 | 状态 |
|---|---|---|---|
| **V1 软件 / 框架正确性** | 模块、插件（plugin）和接口是否按规范运行？ | 单元测试与契约测试（contract tests）；架构导入规则；合成数据结构（schema、约束、关联关系、可复现性、数据溯源（provenance））；指标定义；失败模式（§2–3） | ✅ |
| **V2 框架集成 / Golden Path（黄金路径）** | 整条流水线（pipeline）能否通过每一种客户端接口端到端运行？ | 通过 workflow runner、HTTP Application API 和浏览器 UI 运行的 Golden Path；持久化的数据集与溯源；可复现性；无前视（§2） | ✅ |
| **V3 场景与参考数据验证** | 场景是否按规范运行？框架能否在真实参考数据上正确运行？ | 基于 fixture 的场景行为检查（§4）；基于已提交 M5 子集的检查：规范（canonical）/混合（hybrid）数据验证、描述性校准比较、预测回测、Golden Path 冒烟运行（§4.1） | ✅ 原型层面；参考数据比较仅为**描述性** |
| **V4 真实运营验证** | 合成运营数据及结果对真实仓库是否成立？ | 无 — 需要真实运营数据和试点 | ❌ 未来 — 绝不宣称 |

**M5 数据集不是仓库运营数据。** M5 是门店级零售**销售**数据（Walmart；已提交的子集：门店 CA_1、
部门 FOODS_3、前 50 个商品），附带日历和价格。在本框架中，它是**参考需求/销售环境**：合成需求基于它进行校准，
预测在它上面进行回测。所有运营相关内容 — 仓库、供应商、提前期、成本、期初库存、采购订单 — 均为**合成的**
（即混合验证环境（Hybrid Validation Environment））。此外，销售数据受缺货截断（censored），因此 M5 是需求的代理，
而非真实需求。

早期草案使用层级 1–4（工程、合成数据结构性、场景、真实世界）：层级 1 和 2 对应 V1（覆盖整条流水线的工程检查
归入 V2 报告），层级 3 对应 V3，层级 4 对应 V4。

文档与 UI 中使用的成熟度标签：Demo · Prototype · Synthetic Validation · Real Data Validation ·
Production Validation（演示 · 原型 · 合成数据验证 · 真实数据验证 · 生产验证）。v0.1 仅达到 **Prototype + Synthetic Validation**（原型 + 合成数据验证）。

## 2. V1 与 V2 — 工程与集成检查

| 检查项 | 类别 | 测试位置 |
|---|---|---|
| 包可导入、配置可加载、`/health` 正常 | V1 | unit, integration |
| 注册表（registry）：注册、按 id/version 查找、拒绝重复 | V1 | unit |
| 每个插件通过其契约测试（contract tests）；指标定义；失败模式 | V1 | unit |
| 架构规则 R1–R3（[architecture.md §2](architecture.md)）；UI 不导入任何框架模块 | V1 | unit, ui（导入图测试） |
| API → application → engines → result，端到端 | V2 | integration |
| 通过 workflow runner、HTTP API 和浏览器 UI 运行的 Golden Path（黄金路径）；可复现性；溯源 | V2 | scenario（`test_golden_path.py`），integration（`test_api_golden_path.py`），ui |
| 无前视（No look-ahead）；公平的策略比较 | V2 | integration |

## 3. V1 — 合成数据结构检查

| 检查项 | 判定标准 |
|---|---|
| Schema 一致性 | 所有字段齐全、dtype 正确、无意外空值 |
| 约束 | 100% 声明的约束通过（`ValidationReport.passed`） |
| 取值范围 | 例如 数量 ≥ 0 且为整数，lead_time_std ≤ lead_time_mean，概率位于 [0, 1] |
| 关联关系 | 所有外键均可解析 |
| 可复现性 | 相同输入 + seed → 相同的 `content_hash`；不同 seed → 不同哈希 |
| 溯源完整性 | 记录包含输入、生成器 id/version、参数、场景、seed、变换步骤、输出哈希 |
| 校准合理性（仅描述性，归入 V3 报告） | 报告合成数据与参考数据的均值、方差、零值占比、周内分布；**不**作为通过/失败的等价性结论 |

## 4. V3 — 场景检查（相同 seed，合成需求）

| 检查项 | 判定标准 |
|---|---|
| High Demand（高需求） | 总**期望**需求（noise_scale = 0）/ 基线 ∈ [1.25, 1.35]；抽样总需求明显更高（> 1.15）。在较短的预测期内，更强的季节性也会改变窗口均值（fixture：期望值 1.345，抽样值 1.24，原因是小计数上的 Poisson 噪声） |
| Demand Shock（需求冲击） | 窗口内平均需求 / 窗口内基线 ≈ shock_multiplier（±10%）；窗口外 ≈ 基线（±5%） |
| Supply Disruption（供应中断） | 窗口内下达的采购订单（PO）的平均实际提前期 ≥ 基线 + 5 天；窗口内收货数量 ≤ 订购数量 |
| 仿真有响应 | 对静态策略 `reorder_point`，High Demand 或 Supply Disruption 下的缺货日比率 ≥ 基线 |
| 策略存在差异 | 基线下至少有两种策略在满足率或总成本上存在非平凡差距 |
| 会计恒等式 | 对每个 物品-日：期初 = 前一日期末 + 到货；已满足 + 损失 = 需求；期末 ≥ 0 |
| 指标正确性 | 测试中由台账（ledger）重新计算的指标与报告指标一致 |
| 无前视（No look-ahead） | 修改决策日 D 之后的需求，不会改变预测起点 ≤ D 的预测结果，也不会改变截至 D 的台账行和订单（集成测试） |
| 公平比较 | 通过 `engine.compare` 比较的各策略面对完全相同的需求、供应抽样和 seed |

**Gate 8 验收（负责人，2026-09-27）。** 框架能够在完全相同的受控仿真条件下执行并公平比较多个可互换的补货策略，
结果可复现，且具有明确的时间信息边界。这**并不**意味着声称任何策略（例如 `dynamic`）在现实世界中具有经济或运营上的优越性。

**真实子集运行仅为描述性 / 冒烟测试证据。** 在已提交的 M5 子集（CA_1 / FOODS_3 / 前 50 个商品，91 天合成预测期，
合成运营数据，单一 seed）上的策略结果表明流水线能够在真实参考需求上运行；它们不是经济或算法优越性的证据，
也绝不作为验证结果报告。

上述阈值为初始提案；如需调整，须连同理由记录在开发日志中。

### 4.1 V3 — 参考数据检查（已提交的 M5 子集）

| 检查项 | 判定标准 |
|---|---|
| 规范数据（Canonical data） | M5 适配器（adapter）输出的零售数据包通过全部 schema、约束和键检查（通过/失败） |
| 混合环境（Hybrid environment） | 参考表 + 合成运营数据通过全部检查，外键均可解析（通过/失败） |
| 校准比较 | 合成数据与参考数据的均值、波动、零值占比、周内分布及商品级相关性 — **描述性**，无阈值 |
| 预测回测 | 三个预测插件在参考销售数据上的滚动起点（rolling-origin）WAPE / MAE / bias — 描述性；测试仅断言各插件能运行且 LightGBM 优于移动平均 |
| Golden Path 冒烟运行 | 在参考子集上 4 个场景 × 3 种策略均能完成并可复现 — 结果仅为**描述性**，绝不作为真实世界优越性的证据 |

## 5. 测试数据策略

- V1 / V2 测试使用 `tests/fixtures/m5_like/`：一个小型的、**合成的**、M5 形态的测试夹具（fixture）（1 家门店、
  约 10 个商品、约 3 年），由 `scripts/make_m5_fixture.py` 以固定 seed 生成，并
  标注为 `source_type=fixture`。
- V3 参考数据测试（`-m m5_local`）使用已提交在 `data/reference/m5_subset/` 中的真实 M5 子集
  （负责人批准的例外，CLAUDE.md §13；适用 Kaggle 规则）。这些测试也在 CI 中运行，仅当该文件夹
  不存在时才跳过。

## 6. 验证报告

[`validation-report.md`](../validation-report.md) 由 `uv run python scripts/validation_report.py` 生成：
它运行 V1、V2 和 V3 的测试选集（pytest，按模块统计 JUnit 计数），计算 V3 参考数据结果，
并记录 commit、版本和 seed。报告以明确的"未验证"章节（V4）结尾。每次发布时重新生成；不要手工编辑。
