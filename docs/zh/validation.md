# 验证规范 — v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../validation.md](../validation.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

> v0.1 验证的是**框架**本身，而非合成数据在真实世界中的准确性。
> 允许的表述：*"The framework validates synthetic data generation and scenario execution at the prototype level."*（"该框架在原型层面验证了合成数据生成与场景执行。"）

## 1. 验证层级

| 层级 | 问题 | 是否属于 v0.1？ |
|---|---|---|
| **1 工程（Engineering）** | 模块、API、插件（plugin）及流水线（pipeline）是否正常工作？ | ✅ |
| **2 合成数据（结构性）** | Schema、类型、约束、取值范围、关联关系、可复现性、数据溯源（provenance）是否正确？ | ✅ |
| **3 场景（Scenario）** | 场景是否按规范运行？不同策略是否产生不同结果？ | ✅ |
| **4 真实世界算法 / 数据** | 合成数据能否代表现实？结果在真实业务中是否成立？ | ❌ 未来 — 绝不宣称 |

文档与 UI 中使用的成熟度标签：Demo · Prototype · Synthetic Validation · Real Data Validation ·
Production Validation（演示 · 原型 · 合成数据验证 · 真实数据验证 · 生产验证）。v0.1 仅达到 **Prototype + Synthetic Validation**（原型 + 合成数据验证）。

## 2. 层级 1 — 工程检查

| 检查项 | 测试位置 |
|---|---|
| 包可导入、配置可加载、`/health` 正常 | unit, integration |
| 注册表（registry）：注册、按 id/version 查找、拒绝重复 | unit |
| 每个插件通过其契约测试（contract tests） | unit |
| 架构规则 R1–R3（[architecture.md §2](architecture.md)） | unit（导入图测试） |
| API → application → engines → result，端到端 | integration |
| Golden Path（黄金路径） | scenario |

## 3. 层级 2 — 合成数据检查

| 检查项 | 判定标准 |
|---|---|
| Schema 一致性 | 所有字段齐全、dtype 正确、无意外空值 |
| 约束 | 100% 声明的约束通过（`ValidationReport.passed`） |
| 取值范围 | 例如 数量 ≥ 0 且为整数，lead_time_std ≤ lead_time_mean，概率位于 [0, 1] |
| 关联关系 | 所有外键均可解析 |
| 可复现性 | 相同输入 + seed → 相同的 `content_hash`；不同 seed → 不同哈希 |
| 溯源完整性 | 记录包含输入、生成器 id/version、参数、场景、seed、变换步骤、输出哈希 |
| 校准合理性（仅描述性） | 报告合成数据与参考数据的均值、方差、零值占比、周内分布；**不**作为通过/失败的等价性结论 |

## 4. 层级 3 — 场景检查（相同 seed，合成需求）

| 检查项 | 判定标准 |
|---|---|
| High Demand（高需求） | 总需求 / 基线总需求 ∈ [1.25, 1.35] |
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

## 5. 测试数据策略

- 测试使用 `tests/fixtures/m5_like/`：一个小型的、**合成的**、M5 形态的测试夹具（fixture）（例如 1 家门店、
  1 个品类、10 个商品、约 3 年），由 `scripts/make_m5_fixture.py` 以固定 seed 生成，并
  标注为 `source_type=fixture`。不提交任何真实 M5 数据。
- 可选的本地真实 M5 子集检查：`uv run pytest -m m5_local`（当
  `data/raw/m5_subset/` 不存在时跳过）。

## 6. 验证报告

Phase 14 生成 `docs/validation-report.md`，包含所有层级 1–3 检查的结果、确切的
commit、seed 与配置，以及明确的"未验证"章节（层级 4）。
