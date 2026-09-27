# 场景规格说明（Scenario Specification）— v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../scenario-spec.md](../scenario-spec.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

## 1. 原则：场景 ≠ 算法

**场景**（scenario）是一种显式的、带版本的、经过校验的**环境配置**（需求与
供应条件）。它不包含任何代码。**算法**（预测模型、库存模型、策略）
是独立的插件。任何场景都可以与任何兼容的算法组合：
场景 A × 模型 A、场景 A × 模型 B、场景 B × 模型 A、……

## 2. 通用 `ScenarioSpec`（框架层）

```yaml
scenario_id: high_demand          # snake_case, unique within a pack
version: 1.0.0
pack: warehouse
title: High Demand
description: Sustained 30% demand increase with stronger seasonality.
parameters: {...}                 # validated by the pack's scenario_parameter_model
tags: [demand]
```

场景文件位于 `scenarios/warehouse/src/industrial_ai_warehouse/scenarios/*.yaml`。
用户自定义场景（场景构建器，Scenario Builder）以相同结构存储在 SQLite 中，并标记
`source: user`。规格一旦被某次运行使用即不可变；编辑会创建新版本。

## 3. 仓储场景参数

| 参数 | 类型 | 默认值 | 有效范围 | 作用 |
|---|---|---|---|---|
| `demand_multiplier` | float | 1.00 | 0.10 – 5.00 | 缩放期望需求水平 |
| `seasonality_multiplier` | float | 1.00 | 0.00 – 3.00 | 以 1 为中心缩放季节性振幅（0 = 平稳） |
| `noise_scale` | float | 1.00 | 0.00 – 3.00 | 缩放需求离散度 |
| `shock_multiplier` | float | 1.00 | 0.00 – 10.00 | 冲击窗口内的需求系数 |
| `shock_start_day` | int | 0 | ≥ 0 | 相对预测期起点的偏移天数 |
| `shock_duration_days` | int | 0 | ≥ 0 | 0 = 无冲击 |
| `lead_time_delta` | int（天） | 0 | −30 – 60 | 叠加到供应商平均提前期上（结果下限为 1） |
| `disruption_start_day` | int | 0 | ≥ 0 | 相对预测期起点的偏移天数 |
| `disruption_duration_days` | int | 0 | ≥ 0 | 0 = lead_time_delta 作用于整个预测期 |
| `supply_capacity_factor` | float | 1.00 | 0.00 – 1.00 | 中断窗口内供应商对每笔订货实际发货的比例 |
| `planner_aware` | bool | false | — | 策略看到的是调整后的提前期（true）还是名义提前期（false） |

## 4. 初始场景（恰好四个）

| scenario_id | 参数（非默认值） | 预期行为（已测试） |
|---|---|---|
| `baseline` | — | 基准行为 |
| `high_demand` | demand_multiplier 1.30, seasonality_multiplier 1.20, lead_time_delta 0 | 总需求相比 baseline ↑ 约 30%（相同种子） |
| `demand_shock` | shock_multiplier 2.50, shock_start_day 28, shock_duration_days 14 | 需求仅在窗口内 ↑ |
| `supply_disruption` | lead_time_delta +7, disruption_start_day 28, disruption_duration_days 42, supply_capacity_factor 0.50 | 窗口内实际提前期变长 / 部分到货；静态策略的缺货 ↑ |

以上数值为 v0.1 的建议默认值，可在首次 Golden Path 运行后调整；任何改动都须
提升场景版本。

## 5. 库存仿真模型

由 Warehouse 插件 `inventory_simulation` 1.0.0（`industrial_ai_warehouse.simulation`）实现。
按日离散时间、按单品（product × warehouse）、单级（single-echelon）、缺货损失（lost sales）模型。对预测期内每一天 *t*，
依次执行：

1. **收货（Receive）** — 在 *t* 日到达的发货入库：`opening_on_hand_t = closing_on_hand_{t−1} + arrivals_t`。
2. **需求（Demand）** — `fulfilled_t = min(opening_on_hand_t, demand_t)`，`lost_sales_t = demand_t − fulfilled_t`
   （直接损失，不做延期交货 back-order）。
3. **结存（Close）** — `closing_on_hand_t = opening_on_hand_t − fulfilled_t`。
   （等价于 *Inventory(t+1) = Inventory(t) + Arrivals(t) − Demand(t)*，缺货损失下限为 0。）
4. **盘点（Review）** — 每隔 `review_period_days` 天，策略的 policy 观察 `DailyObservation`
   （在库量、在途量、库存位置 = 在库量 + 在途量、当日需求与已满足量）并返回一个数量；仿真先应用供应商的
   最小订货量，再将其向上取整到箱规。
5. **订货（Order）** — 提前期 `L = max(1, round(mean + lead_time_delta_t + std · z_t))`；以概率
   `1 − on_time_probability` 增加 1–3 天（`max_extra_delay_days`）；到货日为 `t + L`；发货数量为
   `ceil(quantity · supply_capacity_factor_t)`；未发货部分即告损失。`lead_time_delta` 与
   `supply_capacity_factor` 作用于在中断窗口
   `[disruption_start_day, disruption_start_day + disruption_duration_days)` 内下达的订单；当持续时间为 0 时
   作用于整个预测期。若 `planner_aware = true`，策略看到的是调整后的平均提前期。
6. **记录（Record）** — 台账行（`sim.inventory_ledger`）、采购订单（`sim.purchase_order`）与 KPI
   （data-model §6）。

`z_t`、是否延迟及延迟天数均由运行种子**按单品、按日**预先采样，因此在同一种子下比较的各策略面对完全相同的
供应条件（公共随机数，common random numbers）。初始状态：
`ops.initial_inventory`（在库量 = μ · (L̄ + order_cycle/2)，在途量 0）。容量上限
（`ops.warehouse.capacity_units`）超出时仅作为警告报告，不强制执行（v0.1）。
需求侧场景参数由上游的需求生成器应用，因此仿真会在其警告中将它们列为"未应用（not applied）"。

## 6. 预测期需求

- `demand_source = synthetic`：使用基于预测期之前参考历史校准的 `time_series` 生成器，
  并应用场景。
- `demand_source = reference`：使用预测期内的实际参考需求，以确定性方式应用场景乘数/冲击
  （不重采样）；可用作合理性校验（sanity check）。

预测模型仅使用预测期起点**之前**的数据训练，且只能随着逐日观测看到预测期内的需求
（无前视，no look-ahead）。
