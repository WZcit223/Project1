# 范围与非目标 (Scope & Non-goals) — v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../scope.md](../scope.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

> 架构优先、可扩展性优先，场景验证其次；产品化 (Productionization) 留待后续。

## 1. 范围内 (v0.1)

**基础层 (Foundation)：** 数据集接入 (Dataset Ingestion)、数据集模式 (Dataset Schema)、元数据 (Metadata)、数据目录 (Data Catalog)、数据转换 (Data Transformation)、
M5 适配器 (M5 Adapter)、合成数据引擎 (Synthetic Data Engine)、数据溯源 (Provenance)、实体表示 (Entity Representation)。

**仿真 / 智能 (Simulation / Intelligence)：** 需求预测 (Demand Forecasting)（基线 + LightGBM）、库存仿真 (Inventory Simulation)、
补货策略 (Replenishment Strategies)（再订货点 Reorder Point、安全库存 Safety Stock、动态补货 Dynamic）、场景建模 (Scenario Modeling)（4 个场景）、
策略对比 (Strategy Comparison)。

**应用 (Application)：** 仪表盘 (Dashboard)、数据浏览器 (Data Explorer)、合成数据配置、场景构建器 (Scenario Builder)、仿真
执行、结果可视化、轻量级 BI。

**基础设施（轻量级）(Infrastructure)：** HTTP API、配置、日志、版本管理、插件注册表 (Plugin Registry)、
实验/运行元数据 (Experiment/Run Metadata)（SQLite）、验证 (Validation)。

**验证 (Validation)：** 第 1–3 级（工程验证、合成数据结构验证、场景行为验证）。参见
[validation.md](validation.md)。

## 2. 明确的非目标 (v0.1)

本阶段**不**要求也不实现：

1. 证明合成数据在统计、因果或经济意义上与真实工业数据等价。
2. 将合成数据用于生产决策。
3. 生产级部署、SaaS、高可用 (High Availability) 或云基础设施。
4. 完整的因果建模 (Causal Modeling)（仅保证接口兼容）。
5. 高级优化 (Advanced Optimization)（不含优化器；策略基于规则并进行对比）。
6. 复杂的多智能体系统 (Multi-agent Systems)（至多为有限的 意图 → 配置 转换器，P1）。
7. Kubernetes、微服务 (Microservices)、Kafka / 事件流 (Event Streaming)、Spark、分布式系统。
8. 向量数据库 (Vector Databases) 或知识图谱 (Knowledge Graph) 基础设施。
9. 完整的多模态 AI (Multimodal AI) 基础设施。
10. 企业级 IAM / 权限系统。
11. 仓储 (Warehouse) 之外的工业场景（维护 Maintenance、能源 Energy、生产 Production 为未来插件）。
12. 大量合成数据算法（v0.1 中恰好三种）。
13. 最先进 (State-of-the-art) 的预测能力（并非 M5 竞赛解决方案）。
14. React / Node 构建流水线。
15. 使用真实企业数据进行验证（第 4 级）。

范围之外的想法记录到 [future-roadmap.md](future-roadmap.md)，不进入代码。

## 3. 仓储验证案例的范围

| 包含 | 不包含 (v0.1) |
|---|---|
| 按日、商品 × 门店 (item × store) 的需求 | 日内 / 小时级粒度 |
| 单级 (Single-echelon)：门店作为库存点，每个商品对应一个合成供应商 | 多级网络 (Multi-echelon)、配送中心 (DC) ↔ 门店调拨 |
| 缺货损失销售 (Lost Sales) | 缺货延期交付 (Backorders)、替代 (Substitution) |
| 来自合成数据的确定性或随机提前期 (Lead Time) | 供应商选择 / 谈判 |
| 持有成本、订货成本；缺货惩罚单独报告 | 完整损益 (P&L)、定价决策 |
| 4 个场景、3 种策略、2 个预测模型 | 优化器、强化学习 (RL)、因果效应估计 |
| 演示子集（默认 CA_1 × FOODS_3，前 50 个商品） | 全部 30,490 条 M5 序列 |

## 4. 数据范围

| 数据 | 来源 | 是否纳入 Git？ |
|---|---|---|
| M5 销售、价格、日历、事件（子集） | 真实数据，Kaggle M5 | **否** — 仅存放于本地 `data/raw/` |
| M5 格式的测试夹具 (Test Fixture) | 合成（由项目脚本生成） | 是（小规模，标注为合成） |
| 库存、供应商、提前期、采购订单、仓库、补货策略 | 合成 | 按需生成；小样本可提交 |
| 场景配置 | 项目定义 | 是 |
