# 数据模型 — v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../data-model.md](../data-model.md) · 相关：[ADR-003](../adr/ADR-003-m5-canonical-adapter.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

本文档定义：(1) 框架中与领域无关的数据集抽象 (dataset abstraction)；
(2) Warehouse 包 (pack) 使用的规范零售需求模型 (canonical retail-demand model)；(3) 合成运营
实体 (synthetic operational entities)；(4) 仿真输出表；(5) M5 映射；(6) **指标定义 (metric definitions)**。

## 1. 框架数据集抽象（与领域无关，`industrial_ai.foundation`）

### 1.1 `FieldSpec`

| 属性 | 类型 | 说明 |
|---|---|---|
| `name` | str | snake_case 列名 |
| `dtype` | enum | `int`、`float`、`str`、`bool`、`date`、`datetime`、`category` |
| `nullable` | bool | 默认 `false` |
| `unit` | str \| null | 例如 `units`、`USD`、`days` |
| `min` / `max` | number \| null | 闭区间范围约束 |
| `allowed_values` | list \| null | 用于分类字段 |
| `description` | str | 人类可读的含义说明 |

### 1.2 `DatasetSchema`

| 属性 | 类型 | 说明 |
|---|---|---|
| `schema_id` | str | 例如 `retail_demand.sales` |
| `schema_version` | semver str | 任何破坏性变更 (breaking change) 均需升级版本 |
| `fields` | list[FieldSpec] | 有序 |
| `primary_key` | list[str] | 唯一性约束 |
| `foreign_keys` | list[{fields, ref_schema_id, ref_fields}] | 关联关系约束 |
| `time_index` | str \| null | 存放时间轴的字段 |
| `entity_keys` | list[str] | 标识实体序列的字段（例如 `product_id`、`store_id`） |

### 1.3 `Dataset`

| 属性 | 类型 | 说明 |
|---|---|---|
| `dataset_id` | str | 稳定 id，例如 `m5_subset_ca1_foods3` |
| `version` | str | 数据集版本 |
| `schema` | DatasetSchema | |
| `data` | pandas.DataFrame | 驻留内存；以 Parquet 制品 (artifact) 形式持久化 |
| `metadata` | DatasetMetadata | 见下文 |
| `provenance` | ProvenanceRecord | 见 [synthetic-data-api.md §5](synthetic-data-api.md) |

由多张表（例如 sales + prices + calendar）组成的逻辑数据集称为 **`DatasetBundle`**：
`bundle_id`、`version`、`tables: dict[str, Dataset]`、`metadata`、`provenance`。

### 1.4 `DatasetMetadata`

| 属性 | 说明 |
|---|---|
| `name`、`description` | |
| `source_type` | `reference`（真实外部数据）、`synthetic`、`derived`、`fixture` |
| `source` | 例如 `M5 Forecasting Accuracy` |
| `source_url` | |
| `dataset_version` / `download_date` | 用于外部数据源 |
| `license_notes` | 例如 "Kaggle competition rules; do not redistribute"（遵循 Kaggle 竞赛规则；不得再分发） |
| `time_range` | `{start, end}` |
| `row_count`、`entities` | 计算得出 |
| `created_at` | UTC 时间戳 |
| `content_hash` | 规范 Parquet 序列化结果的 SHA-256 |
| `tags` | 自由格式标签（例如 `demo`、`prototype`） |

## 2. 规范零售需求模型（Warehouse 包，`schema_version 1.0`）

框架本身从不接触 M5 列名；这些表由 M5 适配器 (adapter) 生成。

| 表 (schema_id) | 主键 | 字段 |
|---|---|---|
| `retail.region` | region_id | region_id（例如 `CA`）、name |
| `retail.store` | store_id | store_id、region_id → region |
| `retail.category` | category_id | category_id（例如 `FOODS`） |
| `retail.department` | department_id | department_id（例如 `FOODS_3`）、category_id → category |
| `retail.product` | product_id | product_id、department_id → department、category_id → category |
| `retail.calendar` | date | date、week_id、weekday（1=周一…7=周日）、month、year、`snap_<region>`（每个区域一个 bool） |
| `retail.calendar_event` | (date, event_name) | date → calendar、event_name、event_type（`Sporting`、`Cultural`、`National`、`Religious`） |
| `retail.sales` | (date, product_id, store_id) | date、product_id、store_id、quantity（int ≥ 0，`units`） |
| `retail.price` | (week_id, product_id, store_id) | week_id、product_id、store_id、unit_price（float > 0，`USD`） |

说明：
- `retail.sales.quantity` 为**观测销量 (observed sales)**，用作需求参考。当门店缺货时，观测销量会低估
  真实需求；v0.1 仅记录这一局限，不做修正。
- 价格缺失的周（商品尚未上架销售）表现为缺失行，而不是零值。

## 3. 合成运营实体（Warehouse 包）

由合成数据引擎 (Synthetic Data Engine) 生成；全部携带溯源信息 (provenance)，并标记为 `source_type=synthetic`。

| 表 | 主键 | 字段 | 生成器 |
|---|---|---|---|
| `ops.warehouse` | warehouse_id | warehouse_id、store_id → store、capacity_units（int > 0）、holding_cost_rate_annual（0–1） | rule_based |
| `ops.supplier` | supplier_id | supplier_id、lead_time_mean_days（≥ 1）、lead_time_std_days（≥ 0）、on_time_probability（0–1）、order_cost（USD ≥ 0）、min_order_qty（int ≥ 0） | rule_based + statistical |
| `ops.product_supplier` | product_id | product_id → product、supplier_id → supplier、unit_cost（USD > 0；= 参考价格 × 成本比率）、case_pack（int ≥ 1） | rule_based + statistical |
| `ops.initial_inventory` | (product_id, warehouse_id) | on_hand_units（int ≥ 0）、on_order_units（int ≥ 0）、as_of_date | rule_based |
| `ops.replenishment_policy` | (product_id, warehouse_id, strategy_id) | strategy_id、parameters（JSON）、review_period_days（int ≥ 1）、target_service_level（0–1） | rule_based（由需求统计量推导） |
| `ops.synthetic_demand` | (date, product_id, store_id) | 与 `retail.sales` 字段相同，另加 `scenario_id` | time_series |

**提前期 (Lead time)** 以每个供应商的概率分布建模（`ops.supplier`），在仿真中针对每张采购
订单进行抽样；实际实现的提前期记录在每张采购订单上。

## 4. 仿真输出表

| 表 | 主键 | 字段 |
|---|---|---|
| `sim.inventory_ledger` | (run_id, strategy_id, date, product_id) | opening_on_hand、arrivals、demand、fulfilled、lost_sales、closing_on_hand、on_order、inventory_position、order_qty |
| `sim.purchase_order` | (run_id, strategy_id, po_id) | product_id、supplier_id、order_date、quantity、sampled_lead_time_days、expected_arrival_date、received_date、received_qty、status（`open`、`received`、`partially_received`） |
| `sim.forecast` | (run_id, model_id, origin_date, date, product_id) | forecast_qty、actual_qty（事后回填） |
| `sim.metrics` | (run_id, strategy_id, metric_id, scope) | value、unit、scope（`total` 或 `product:<id>`） |

## 5. M5 → 规范模型映射

参考：Kaggle M5 Forecasting Accuracy。v0.1 使用 `calendar.csv`、`sell_prices.csv` 和
`sales_train_evaluation.csv`（`sales_train_validation.csv` 的超集：天数 d_1…d_1941，
2011-01-29 … 2016-05-22）。

| M5 | 规范模型 |
|---|---|
| `calendar.date` | `retail.calendar.date` |
| `calendar.d` (`d_1` …) | 仅作连接键 (join key)；用于将销量宽表转换为长表 (unpivot) |
| `calendar.wm_yr_wk` | `retail.calendar.week_id`、`retail.price.week_id` |
| `calendar.wday` (1 = Saturday) | `weekday` 按 ISO 重新编码（1 = 周一） |
| `calendar.event_name_1/_2`、`event_type_1/_2` | `retail.calendar_event` 中的行 |
| `calendar.snap_CA/TX/WI` | `snap_CA/TX/WI` |
| `sales.item_id` | `product_id` |
| `sales.dept_id`、`cat_id`、`store_id`、`state_id` | department_id、category_id、store_id、region_id |
| `sales.d_*` 值 | `retail.sales.quantity` |
| `sell_prices.sell_price` | `retail.price.unit_price` |

子集抽取（`scripts/make_m5_subset.py`，由用户在本地运行）：按门店、品类/部门以及总销量
前 N 的商品进行过滤；以原始 M5 布局输出小型 CSV 至 `data/raw/m5_subset/`，并附带
`SOURCE.json`，记录过滤条件、源文件哈希及下载日期。

## 6. 指标定义

除非 scope 另有说明，所有指标均按每次运行 (run) 的每个策略在**仿真期间 (simulation horizon)**
内计算，并对所有仿真的商品-日 (item-day) 进行汇总。记号：对商品 *i*、第 *t* 天：
需求 *Dᵢₜ*，满足量 *Fᵢₜ = min(Dᵢₜ, available)*，损失量 *Lᵢₜ = Dᵢₜ − Fᵢₜ*，期末在库量 *Iᵢₜ*，
单位成本 *cᵢ*，单价 *pᵢₜ*，年持有成本率 *h*，订货成本 *k*，期间长度 *T* 天，
商品数 *N*。

| 指标 id | 名称 | 定义 | 单位 |
|---|---|---|---|
| `demand_total` | 需求量 (Demand) | Σ Dᵢₜ | units |
| `service_level` | 服务水平 (Service level / **fill rate**，满足率) | Σ Fᵢₜ / Σ Dᵢₜ（若 Σ D = 0 则无定义 → 报告为 `null`） | 比率 0–1 |
| `stockout_rate` | 缺货率 (Stockout rate) | #{(i,t) : Lᵢₜ > 0} / (N · T) | 比率 0–1 |
| `lost_sales_units` | 损失销量 (Lost sales) | Σ Lᵢₜ | units |
| `lost_sales_value` | 损失销售额 (Lost sales value)（单独报告，**不**计入库存成本） | Σ Lᵢₜ · pᵢₜ | USD |
| `avg_inventory_units` | 平均库存水平 (Average inventory level) | (1 / T) Σₜ Σᵢ Iᵢₜ | units |
| `avg_inventory_value` | 平均库存价值 (Average inventory value) | (1 / T) Σₜ Σᵢ Iᵢₜ · cᵢ | USD |
| `holding_cost` | 持有成本 (Holding cost) | Σ Iᵢₜ · cᵢ · h / 365 | USD |
| `ordering_cost` | 订货成本 (Ordering cost) | （采购订单数）· k | USD |
| `inventory_cost` | 库存成本 (Inventory cost) | `holding_cost` + `ordering_cost` | USD |
| `order_frequency` | 订货频率 (Order frequency) | （采购订单数）/ (N · T / 7) | 每商品每周订单数 |
| `inventory_turnover` | 库存周转率 (Inventory turnover)（年化） | (Σ Fᵢₜ · cᵢ) / `avg_inventory_value` · 365 / T（若平均价值 = 0 则报告为 `null`） | 次 / 年 |

商品采购成本不计入库存成本（在满足需求相同的前提下，除期末库存外，各策略的采购成本
相同）。预测准确度指标（MAE、RMSE、WAPE，以及可选的 M5 WRMSSE 作为参考）由预测插件
(forecast plugin) 单独报告。
