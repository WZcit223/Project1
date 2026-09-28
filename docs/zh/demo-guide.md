# 演示指南（Demo Guide）— v0.1

状态：**Phase 15（Gate 13 草案）** · English (authoritative): [../demo-guide.md](../demo-guide.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

本指南回答一个问题：*其他人能否理解该框架、运行 Golden Path（黄金路径）、复现结果，并理解哪些内容已经验证、
哪些尚未验证？*

> **你看到的是什么。** 一个**原型**框架（数据 → 合成数据 → 预测 / 仿真 → 场景 / 策略 → 应用）。
> 仓库案例将**真实的参考销售数据**（一个小型 M5 子集）与**合成运营数据**相结合。结果展示的是各策略在相同、
> 受控的仿真条件下的比较 — 它们**不是**真实世界表现的证据
> （[验证报告](../validation-report.md)，V4 类别未执行）。

## 0. 这是什么

*本原型通过一个**库存需求预测与补货**场景，展示一个**工业 AI 应用框架**，使用 M5 作为参考需求数据，并结合
合成运营数据。* 它不是仓储产品，也没有被证明能改进任何真实运营。

| | 框架（`src/industrial_ai/`） | 场景包（`scenarios/warehouse/`） |
|---|---|---|
| 角色 | 可复用、与领域无关的基础组件 | 一个仅基于框架公开 API 构建的验证案例 |
| 包含 | 数据集 + 溯源、合成数据生成器、预测插件、仿真引擎、场景注册表、工作流运行器、Application API | M5 适配器、零售 / 运营 schema、库存仿真、补货策略、四个场景 |
| 规则 | 从不导入场景包（由测试强制保证） | 可替换：其他领域就是另一个场景包 |

**为什么选择库存？** 需求预测与补货是一个被充分理解的工业决策问题，并且有公开的、接近需求的真实数据
（M5 销量）。它覆盖框架的每一层——参考数据、合成数据、预测、仿真、策略、场景、结果——因此是检验框架的
好案例，而不是项目本身的目标。

## 1. 快速开始（约 5 分钟）

前提条件：[uv](https://docs.astral.sh/uv/)、Python 3.11+、本仓库的一个克隆（其中包含
位于 `data/reference/m5_subset/` 的小型 M5 参考子集；适用 Kaggle 规则 — 请勿再分发）。
所有命令都在仓库根目录下运行；运行结果保存在被 Git 忽略的 `data/processed/` 中。

```bash
uv sync                                  # locked environment (framework, warehouse pack, UI)
uv run python scripts/demo.py            # scripted Golden Path via the Application API (~20 s)
uv run python scripts/serve.py           # API + UI; open http://127.0.0.1:8000/ui/
```

可选检查：`uv run pytest`（完整测试套件，约 2–3 分钟）以及
`uv run python scripts/validation_report.py`（重新生成验证报告，约 3 分钟）。

## 2. 三类数据 — 请区分清楚

| 类型 | 内容 | 位置 | 是否真实？ |
|---|---|---|---|
| **参考数据** | M5 门店级零售**销售**数据（Walmart 门店 CA_1、部门 FOODS_3、前 50 个商品）、日历、价格 | `data/reference/m5_subset/` | 真实，但为**观测销量**而非需求，且**不是仓库运营数据** |
| **合成数据** | 按场景生成的预测期需求（基于参考数据校准）、仓库、供应商、提前期、成本、初始库存、补货设置；采购订单和库存由仿真产生 | 每次运行时生成，连同溯源（provenance）存储在数据集目录（catalog）中 | 合成 |
| **测试夹具（fixture）** | 大多数测试使用的小型 M5 形态**合成**数据集 | `tests/fixtures/m5_like/` | 合成 |
| *真实运营数据* | *库存快照、采购订单历史、真实提前期与成本* | *不可用* | *V4 所需（未来）* |

M5 不含库存信息：零观测销量可能是真实的零需求、缺货或其他形式的需求截断（censoring），数据无法区分这些原因——**零观测销量 ≠ 已确认的缺货**。

## 3. 浏览器中的演示流程（5–10 分钟）

启动 `uv run python scripts/serve.py` 并打开 `http://127.0.0.1:8000/ui/`。每个页面都显示
"Prototype · Synthetic data" 标识。

| 步骤 | 页面 | 操作 | 要点 |
|---|---|---|---|
| 1 | **Overview（概览）** | （首次启动时为空） | UI 只调用应用 API（Application API）；该标识将所有内容标记为原型 / 合成 |
| 2 | **Scenario builder（场景构建器）** | 查看 `high_demand`、`demand_shock`、`supply_disruption`；可选：保存一个新场景（例如 7 天内冲击 ×1.8） | 场景是配置而非代码；取值依据场景包（pack）的参数范围进行校验；版本不可变 |
| 3 | **Simulation（仿真）** | 保持默认值——参考数据 `m5_subset`、场景 `baseline`、预测 `seasonal_naive`、全部三种策略、91 天、seed 20260927——然后 **Run**（约 6 秒） | 三种策略面对相同的需求与供应抽样；默认值即文档中的演示配置 |
| 4 | **Results（结果）**（运行页面） | KPI 表格和图表 | 满足率与成本的对比；订货 / 持有 / 缺货损失成本分别列示 |
| 5 | **Simulation（仿真）** | 相同设置，场景 `high_demand` → Run | 相同的 seed 与需求流；只有场景不同 |
| 6 | **Results → Compare（结果 → 对比）** | 勾选两次运行 → Compare selected runs | *如果环境发生变化，每种策略下会发生什么？* |
| 7 | **What-if（假设分析）**（基线运行页面） | `lead_time_delta` = 5 → Re-run | 相同的参考数据、场景版本和 seed；只改变一个参数 |
| 8 | **Data（数据）** | 打开某次运行的库存台账或合成需求 | 来源类型标识（reference、synthetic、derived）；溯源：生成组件、seed、场景、按哈希标识的输入 |
| 9 | **Synthetic data（合成数据）**（可选） | 生成预填的示例 | 任何生成器都可以通过 API 驱动；结果连同溯源一起登记 |

结束语：*同一个框架可以导入参考数据、生成受控的合成环境、运行多次仿真，并支持基于场景的运营决策分析 —
已在原型层面得到验证。*

## 4. Golden Path 详解（点击 "Run" 时发生了什么）

```
UI form ─► POST /api/runs ─► ApplicationService ─► WorkflowRunner ─► WarehousePack.run
  1 load reference   M5 files → canonical retail bundle (schema checks)        [reference]
  2 operations       rule_based / statistical generators → warehouses, suppliers, lead times, costs [synthetic]
  3 scenario demand  time_series generator calibrated on reference sales, scenario applied        [synthetic]
  4 demand timeline  observed history + synthetic horizon (forecasts never see the future)
  5 forecast         seasonal naive | moving average | LightGBM, rolling origins with 56-day warm-up
  6 simulate         inventory simulation × strategies (reorder point, safety stock, dynamic)
  7 metrics          fill rate, stockout-day rate, ordering / holding / lost-sales / total cost …
  8 persist          run record + every dataset with provenance in the catalog (SQLite + Parquet)
```

分层：UI → 应用 API → 应用层 → 合成 / 仿真引擎 → 插件 → 数据集
（[architecture.md](architecture.md)）。仓库逻辑位于场景包中；框架从不导入它。

## 5. 演示场景与预期输出

脚本化演示（`scripts/demo.py`）在 M5 子集上运行 `baseline` 和 `high_demand`（需求 ×1.3，季节性更强）
以及一个假设分析（`lead_time_delta` +5 天），预测期 91 天，seed 20260927，使用季节性朴素（seasonal naive）预测。
在相同的 commit 和 seed 下，你会得到与
[验证报告 §3.2](../validation-report.md) Golden Path 表格完全相同的数值（`tests/integration/test_demo.py` 检查
演示能否复现该报告，以及本表是否与之一致）：

| Scenario | Strategy | Fill rate | Total cost |
|---|---|---|---|
| baseline | reorder_point | 84.7% | $39,248 |
| baseline | safety_stock | 86.2% | $36,995 |
| baseline | dynamic | 93.8% | $29,136 |
| high_demand | reorder_point | 74.3% | $70,030 |
| high_demand | safety_stock | 76.9% | $62,865 |
| high_demand | dynamic | 89.9% | $39,865 |

如何解读：所有策略面对相同的需求与供应抽样，因此差异来自策略本身。缺货损失成本按完整售价计价（一种上界代理），
因此总成本会偏向持有更多库存的策略；订货成本反映合成设定的每单 20–60 USD。
UI 仿真页面的默认表单使用相同配置（季节性朴素法、91 天、seed 20260927），显示相同的数值；选择其他预测模型（如 LightGBM）会得到不同但同样可复现的数值。

## 6. 已验证与未验证的内容（V1–V4）

| 类别 | 含义 | v0.1 |
|---|---|---|
| **V1** 软件 / 框架正确性 | 模块、插件、接口、数据结构、指标均按规范运行 | ✅ 通过 |
| **V2** 框架集成 / Golden Path | 流水线通过 runner、HTTP API 和 UI 端到端运行；可复现；无前视 | ✅ 通过 |
| **V3** 场景与参考数据验证 | 场景按规范运行；框架在真实参考子集上正确运行；与参考数据的比较为描述性 | ✅ 通过（比较为描述性） |
| **V4** 真实运营验证 | 结果对真实仓库成立 | ⛔ 未执行 |

测试数量和全部数值见生成的[验证报告](../validation-report.md)；定义见
[validation.md](validation.md)。
通过 V1–V3 意味着框架作为原型可以正常工作；**不**意味着任何策略在现实中更优。

## 7. 复现结果

- 相同输入 → 相同输出：参考子集（经哈希校验）、生成器和插件版本、参数、场景（id + version + overrides）
  以及 **seed**。运行 id 会不同；指标和数据集内容哈希不会不同。
- 重新运行已存储的运行：将其 `pack`、`reference_id`、`scenario_id`、固定的 `scenario.version`、`seed`、
  `horizon_days`、`options` 和 `scenario_overrides` 提交到 `POST /api/runs`（[application-api.md](application-api.md) §1）。
- 每个数据集的溯源（`GET /api/datasets/{id}`）都以内容哈希标明其输入，并记录生成组件及其版本、参数、场景和 seed。
- 重新生成证据：`uv run python scripts/validation_report.py`。

## 8. 已知局限

- 合成运营数据未基于任何真实公司进行校准；成本和提前期是看似合理的占位值
  （例如每单 20–60 USD 的订货成本在库存成本中占主导）。
- 合成需求的零销量天数远少于 M5 参考数据，且其均值高于参考数据均值（在有销量的天数上接近）— 数据见验证报告 §3.2。
  M5 中的零观测销量无法归因于缺货或真实的零需求。零值连续段建模已列入路线图。
- 单级（single echelon）、缺货损失（lost sales）、按日；教科书式策略，未做优化；各策略的调整频率按设计不同
  （[plugin-spec](plugin-spec.md) §4）。
- 冷启动：没有销售历史的商品永远不会被补货。
- 运行为同步执行；单用户演示；无身份认证；英文 UI；图表图例可能重叠（仅外观问题）。
- `demand_source = reference`（回放参考需求）尚未实现。
