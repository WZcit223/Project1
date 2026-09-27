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

数据集通过 `build_dataset(dataset_id, version, schema, data, source, lineage)` 创建：该函数按 Schema 顺序重排列，并根据数据本身**计算**行数、内容哈希、时间范围、实体计数以及溯源输出。`Dataset` 在构造时会重新校验这些不变量，因此其元数据与溯源永远不会与数据不一致。数值层面的校验另行进行（`validate_dataset`，见 §1.5）。

由多张表（例如 sales + prices + calendar）组成的逻辑数据集称为 **`DatasetBundle`**：
`bundle_id`、`version`、`tables: dict[str, Dataset]`、`source`、`lineage`；其 `content_hash` 由各成员表的名称与哈希推导得出。

### 1.4 `DatasetMetadata`

| 属性 | 说明 |
|---|---|
| `name`、`description` | 由生产者提供的字段（`SourceInfo`）：name … tags |
| `source_type` | `reference`（真实外部数据）、`synthetic`、`derived`、`fixture` |
| `source` | 例如 `M5 Forecasting Accuracy` |
| `source_url` | |
| `dataset_version` / `download_date` | 用于外部数据源 |
| `license_notes` | 例如 "Kaggle competition rules; do not redistribute"（遵循 Kaggle 竞赛规则；不得再分发） |
| `time_range` | `{start, end}` |
| `row_count` | 计算得出 |
| `entity_counts` | 计算得出：每个实体键的不同取值数，例如 `{"product_id": 50}` |
| `created_at` | UTC 时间戳 |
| `content_hash` | 计算得出：按列（按名称排序、逻辑数据类型族、保留行顺序、忽略索引）对值计算 `sha256:`；Parquet 往返后保持不变 |
| `tags` | 自由格式标签（例如 `demo`、`prototype`） |

### 1.5 校验（`industrial_ai.foundation.validation`）

`validate_dataset(dataset, constraints=(), references=None)` 与 `validate_bundle(bundle, constraints)`
返回 `ValidationReport`（`subject`、`results`、计算得出的 `passed`）。每个 `CheckResult` 包含 `check`、`target`、`status`（`passed` / `failed` / `skipped`）、`violations`（违规行数）和 `message`。

| 检查 | 来源 | 规则 |
|---|---|---|
| `dtype` | Schema | 列与逻辑类型一致（`date` 值不得带时间部分；`str` 值必须为字符串） |
| `not_null` | Schema（`nullable=false`）/ 约束 | 无缺失值 |
| `range` | Schema `min`/`max` / 约束 | 数值在上下限内；若该列类型错误则**跳过** |
| `allowed_values` | Schema | 值属于允许集合 |
| `primary_key` | Schema | 无重复、无空键 |
| `foreign_key` | Schema / 约束 | 每个键都存在于被引用表中；未提供被引用表时**跳过**（Bundle 会提供其自身的各表） |
| `unique`、`integer`、`relation` | 约束 | 字段唯一；数值为整数；逐行比较 `left op right` |

校验从不修改数据，也不会因数据有误而抛出异常。`skipped` 的检查不会使报告失败，但始终会被列出，因此不会有任何检查被悄悄视为通过。

### 1.6 数据目录（`industrial_ai.foundation.catalog.DatasetCatalog`）

SQLite（通过 SQLModel；`IAI_DATABASE_URL`）为每个数据集与每个 Bundle 保存一行记录，其中 Schema、元数据与溯源以 JSON 存储；数据本身为 Parquet 文件，位于
`<IAI_DATA_DIR>/processed/artifacts/datasets/<dataset_id>/<version>/data.parquet`。

| 操作 | 行为 |
|---|---|
| `register(dataset)` | 写入 Parquet，并在提交前**重新读取、校验内容哈希**；重复的 `(dataset_id, version)` → `DatasetAlreadyRegisteredError` |
| `get(dataset_id, version=None)` | 重建 `Dataset`，并重新校验哈希，因此被修改过的数据文件会引发 `DatasetError`；`version=None` 表示最近注册的版本 |
| `list(source_type=None)` | 按注册顺序返回 `DatasetSummary` |
| `preview(dataset_id, version=None, limit=50)` | 概要、逐列统计（数据类型、空值数、最小/最大值、均值）以及前若干行（JSON 安全的字典） |
| `register_bundle(bundle)` / `get_bundle(...)` | 保存成员表的引用；已注册且内容相同的表会被复用，内容冲突的表会被拒绝 |

数据集版本为自由格式字符串（例如 `"1"`、`"2026-09-27"`）；插件与 Schema 版本为语义化版本。

### 1.7 数据导入（`industrial_ai.foundation.ingestion`）

- `load_table(path, schema, dataset_id=…, version=…, source=…)` 读取 `.csv` 或 `.parquet` 文件，其列必须与 Schema 字段完全一致。CSV 文本按逻辑类型转换（`int` → `int64`，若含缺失值则为 `Int64`；`bool` 接受 true/false/1/0/yes/no；日期为 ISO 8601）。无法转换的值会引发 `IngestionError`，并指明列名与示例值——绝不会被悄悄转为缺失值。溯源会记录加载器（`tabular_loader` 1.0.0）、文件名、格式以及文件的 SHA-256（不记录与机器相关的路径）。
- `DatasetAdapter` 协议（`adapter_id`、`adapter_version`、`description`、`load(source) → DatasetBundle`）以及 `new_adapter_registry()`。具体适配器（例如 M5）位于场景包中（ADR-003）。

## 2. 规范零售需求模型（Warehouse 包，`schema_version 1.0`）

框架本身从不接触 M5 列名；这些表由 M5 适配器 (adapter) 生成。

| 表 (schema_id) | 主键 | 字段 |
|---|---|---|
| `retail.region` | region_id | region_id（例如 `CA`）、name |
| `retail.store` | store_id | store_id、region_id → region |
| `retail.category` | category_id | category_id（例如 `FOODS`） |
| `retail.department` | department_id | department_id（例如 `FOODS_3`）、category_id → category |
| `retail.product` | product_id | product_id、department_id → department、category_id → category |
| `retail.calendar` | date | date、week_id、weekday（1=周一…7=周日）、month、year |
| `retail.calendar_snap` | (date, region_id) | date → calendar、region_id → region、snap_active（bool）。采用长表格式，使日历不必硬编码区域 |
| `retail.calendar_event` | (date, event_name) | date → calendar、event_name、event_type（`Sporting`、`Cultural`、`National`、`Religious`） |
| `retail.sales` | (date, product_id, store_id) | date、product_id、store_id、quantity（int ≥ 0，`units`） |
| `retail.price` | (week_id, product_id, store_id) | week_id、product_id、store_id、unit_price（float > 0，`USD`） |

说明：
- `retail.sales.quantity` 为**观测销量 (observed sales)**，用作需求参考。当门店缺货时，观测销量会低估
  真实需求；v0.1 仅记录这一局限，不做修正。
- 价格缺失的周（商品尚未上架销售）表现为缺失行，而不是零值。

## 3. 合成运营实体（Warehouse 场景包，Schema 版本 1.0.0）

由 `industrial_ai_warehouse.generators.generate_operations(retail, seed, config)` 通过合成数据引擎生成；所有表都带有溯源信息，并标注为 `source_type=synthetic`。每一项假设都是 `OperationsConfig` 的一个字段（默认值见下表），并记录在 Bundle 的 lineage 中；每张表都使用由本次运行种子派生出的独立种子。

| 表 | 主键 | 字段 | 生成器 · 规则 |
|---|---|---|---|
| `ops.warehouse` | warehouse_id | warehouse_id（`WH01`…）、store_id → store、capacity_units（int ≥ 1）、holding_cost_rate_annual（0–1） | rule_based · 每家门店一个；容量 = 60 天 × 门店需求 + 1；持有成本率 0.25 |
| `ops.supplier` | supplier_id | supplier_id（`SUP001`…）、order_cost（USD ≥ 0）、min_order_qty（int ≥ 0） | rule_based · 5 家供应商；订货成本 U(20, 60)；最小起订量 ∈ {0, 6, 12} |
| `ops.supplier_lead_time` | supplier_id | supplier_id → supplier、lead_time_mean_days（≥ 1）、lead_time_std_days（≥ 0，≤ 均值）、on_time_probability（0–1） | statistical · 均值 ~ Gamma(9, 0.7) ≥ 2 天；标准差 U(0.5, 2)；秩相关 0.5；准时率 U(0.85, 0.99) |
| `ops.product_supplier` | product_id | product_id → product、supplier_id → supplier、unit_cost（USD > 0）、case_pack（int ≥ 1） | rule_based · 随机分配供应商；unit_cost = 平均售价 × 0.7；箱规 ∈ {6, 12, 24} |
| `ops.initial_inventory` | (product_id, warehouse_id) | on_hand_units（int ≥ 0）、on_order_units（int ≥ 0）——仿真开始时的状态 | rule_based · 在库 = round(μ × (L̄ + 订货周期/2))；在途 0 |
| `ops.replenishment_policy` | (product_id, warehouse_id) | review_period_days（≥ 1）、order_cycle_days（≥ 1）、target_service_level（0.5–0.9999） | rule_based · 1、14、0.95——与策略无关；各补货策略据此推导自身参数 |
| `ops.synthetic_demand` | (date, product_id, store_id) | 与 `retail.sales` 字段相同，另加 `scenario_id` | time_series · `generate_synthetic_demand()`：基于 `retail.sales` 校准，`demand_multiplier → level_multiplier` |

派生表（`source_type=derived`，组件 `warehouse.derive` 1.0.0）是作为生成器输入的确定性汇总：`derived.product_price`（每个商品的平均周售价）、`derived.store_demand`（每家门店各商品日均需求之和）以及 `derived.planning_input`（μ = 最近 365 个有效天的日均需求，排除首次销售前的零值；供应商平均提前期 L̄；初始库存目标）。`build_hybrid_bundle(retail, ops)` 将真实参考表与合成表合并为混合验证环境（Hybrid Validation Environment）；其所有外键都能在 Bundle 内部解析。

**提前期（Lead time）** 是每个供应商的分布（`ops.supplier_lead_time`），在仿真中按每张采购订单抽样；实际提前期记录在每张采购订单上。同一次运行中所有场景的合成需求使用**同一随机数流**（公共随机数，common random numbers），因此场景之间的差异不是抽样噪声。

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
| `calendar.snap_CA/TX/WI` | 每个日期、每个区域一行 `retail.calendar_snap` |
| `sales.item_id` | `product_id` |
| `sales.dept_id`、`cat_id`、`store_id`、`state_id` | department_id、category_id、store_id、region_id |
| `sales.d_*` 值 | `retail.sales.quantity` |
| `sell_prices.sell_price` | `retail.price.unit_price` |

适配器（`industrial_ai_warehouse.adapters.m5.M5Adapter`，id `m5` v1.0.0）：读取包含 `calendar.csv`、`sell_prices.csv`、`sales_train_evaluation.csv`（若无则用 `sales_train_validation.csv`）以及可选 `SOURCE.json` 的目录；返回包含十张规范表（`<dataset_id>.<table>`）的 `DatasetBundle`，各表按主键排序，因此相同输入始终得到相同哈希。以下情况会引发 `IngestionError`：缺少文件或列、`wday` 与日期不一致、缺少 `snap_<STATE>` 列、销量中的日期不在日历中。若没有 `SOURCE.json`，数据被视为 Kaggle 原始文件（`source_type=reference`、数据集 id 为 `m5`、下载日期未知）。价格仅保留销量文件中存在的商品/门店序列。适配器面向子集设计。

子集抽取（`scripts/make_m5_subset.py`，由数据所有者在本地对完整 Kaggle 文件运行）：

```bash
uv run python scripts/make_m5_subset.py --input <存放 Kaggle CSV 的文件夹> --download-date YYYY-MM-DD
# 默认值：--store CA_1 --department FOODS_3 --top-n 50 --output data/raw/m5_subset
```

脚本分块流式读取大文件，保留所选门店 / 部门 / 品类以及总销量前 N 的商品（销量相同时按商品 id 排序），逐字复制原始值（日历文件逐字节复制），并写出 `SOURCE.json`（`source_type=reference`），记录过滤条件、每个原始文件的 SHA-256 以及下载日期。输出是真实的 M5 数据：保存在被 Git 忽略的 `data/raw/` 中。存在该目录时，`uv run pytest -m m5_local` 会对其进行转换和校验。

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
