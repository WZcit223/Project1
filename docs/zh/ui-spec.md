# UI 规格说明（UI Specification）— v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../ui-spec.md](../ui-spec.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

## 1. 原则

- **受众：** 运营经理（Operations Manager）与管理层。展示运营状态、KPI、场景、假设分析（what-if）
  和策略对比，而非模型内部细节。技术细节置于"详情（Details）"折叠区之后。
- **独立性：** UI 仅调用应用 API（Application API，[application-api.md](application-api.md)）。
  可在不改动后端的情况下替换为 React / 移动端。
- **技术栈：** 服务端渲染的 Jinja2 + HTMX；一个小型图表库，随仓库内置（vendored，无需 Node 构建）。
- **诚实标签：** 每个包含结果的页面都显示"Prototype · Synthetic data"徽标；合成
  数据集在视觉上与参考数据加以区分。
- **语言：** v0.1 中 UI 为英文；标签统一存放在一个消息目录（message catalog）中，以便日后添加中文 UI。

## 2. 页面

| # | 页面 | 展示 / 功能 | 使用的 API |
|---|---|---|---|
| 1 | **Overview（概览）** | 最近（或所选）运行的 KPI 卡片：库存价值、服务水平、缺货率、库存成本、库存周转率；需求趋势图；各策略的库存状态 | `GET /api/runs`, `/results`, `/timeseries` |
| 2 | **Data（数据）** | 参考数据集与合成数据集；元数据（来源、版本、溯源摘要）；简单字段列表；数据预览表 | `GET /api/datasets`, `/preview` |
| 3 | **Synthetic Data（合成数据）** | 选择参考数据集、生成器、场景、参数（表单由参数 JSON schema 渲染）、规模、种子 → 生成；展示校验报告和溯源信息 | `GET /api/synthetic/generators`, `POST /api/synthetic/generate` |
| 4 | **Scenario Builder（场景构建器）** | 需求场景（Normal / High Demand / Demand Shock）与供应场景（Normal / Disruption）预设；在有效范围内调整参数；另存为新场景 | `GET/POST /api/scenarios` |
| 5 | **Simulation（仿真）** | 选择数据集、预测模型、策略（一个或多个）、场景、预测期、种子 → 运行 | `GET /api/models`, `/api/strategies`, `POST /api/runs` |
| 6 | **Results（结果）** | KPI 对比表（策略 × KPI，以及跨运行的场景 × KPI）；库存随时间变化、需求随时间变化及缺货事件图表；数据表；假设分析：修改一个参数并重新运行 | `GET /api/runs/{id}/results`, `/timeseries`, `/api/runs/compare` |

## 3. 管理层对比视图（Results）

```
                    Baseline   High Demand   Demand Shock   Supply Disruption
Service level          96%        91%            …               …
Stockout rate           4%         9%            …               …
Inventory cost        …          …              …               …
Orders / item / week  …          …              …               …
```
（示意）

核心信息：*当环境发生变化时，每种策略下会出现什么结果。*

## 4. 轻量级 BI（P1）

在浏览器中或通过一个小型 UI 侧辅助工具，对结果表进行筛选、分组、聚合、排序、透视及基础统计。
**不可审计的展示工具**：正式 KPI 始终来自应用 API；BI 视图标注为"探索性（exploratory）"。

## 5. 演示流程（≤ 5 分钟）

Overview → Scenario Builder（选择 High Demand）→ Synthetic Data（生成）→ Simulation（运行三种
策略）→ Results（对比）→ What-if（修改提前期，重新运行）→ 结束语：
*"同一框架可摄取参考数据、生成受控的合成环境、运行多种仿真，并支持基于场景的运营决策分析。"*
