# 应用 API（Application API）— v0.1

状态：**已于 Gate 0 批准（2026-09-27）；已在 Phase 12 实现** · English (authoritative): [../application-api.md](../application-api.md) · 相关：[ADR-001](../adr/ADR-001-api-first.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

应用 API 是 UI（以及未来任何 React / 移动端 / 企业级客户端）使用的**唯一**接口。采用 HTTP + JSON，
由 FastAPI 在 `/api` 下提供服务，OpenAPI 模式（schema）位于 `/api/openapi.json`，交互式文档位于
`/api/docs`。本地启动：`uv run python -m industrial_ai.api`。

## 1. 约定

- 资源 id 为字符串；版本为语义化版本（semver）字符串。
- 长耗时操作（数据生成、运行）在 **v0.1 中为同步执行**（演示子集的一次运行耗时数秒），但会返回
  带有 `status` 的资源，以便日后改为异步而不破坏客户端兼容性。
- 错误格式：`{"error": {"code": "...", "message": "...", "details": {...}}}`：

  | HTTP | code | 何时 |
  |---|---|---|
  | 404 | `NOT_FOUND`, `RUN_NOT_FOUND`, `DATASET_NOT_FOUND` | 未知的场景包 / 场景 / 组件、运行、数据集 |
  | 409 | `CONFLICT` | 场景 `(id, version)` 或数据集 id 已存在（规格不可变） |
  | 422 | `VALIDATION_ERROR` | 请求体 / 查询参数未通过请求模型校验（`details.errors`） |
  | 422 | `INVALID_RUN_REQUEST`, `INVALID_SCENARIO`, `INVALID_GENERATION_REQUEST`, `CONSTRAINT_VIOLATION` | 语义上无效的请求 |
  | 400 | `BAD_REQUEST` | 其他框架错误（例如未知的结果表） |
  | 500 | `RUN_FAILED` | 运行的流水线抛出异常；该运行以 `failed` 状态保存，`details.run_id` 给出其 id |
  | 500 | `INTERNAL_ERROR` | 意外错误（记录日志；响应中不暴露内部细节） |

- 溯源（provenance）：一次运行以 `(dataset_id, version, content_hash)` 列出其 `inputs` 和 `outputs`；
  `GET /api/datasets/{dataset_id}` 返回每个数据集完整的溯源记录。
- 参考数据通过已配置的**参考数据 id**（`IAI_REFERENCE_DIRS`）选择；客户端从不发送文件路径。
- v0.1 不提供身份认证（非目标）；API 默认绑定到 localhost。

## 2. 端点（已实现）

| 方法与路径 | 用途 |
|---|---|
| `GET /health` | `{"status": "ok", "version": "0.1.0"}` |
| `GET /api/scenario-packs` | 已安装的场景包，含描述和场景 id |
| `GET /api/references` | 已配置的参考数据 id 及其数据是否可用 |
| `GET /api/datasets?source_type=` | 数据目录列表 |
| `GET /api/datasets/{dataset_id}?version=` | 摘要、模式、元数据、溯源信息 |
| `GET /api/datasets/{dataset_id}/preview?limit=50&version=` | 前若干行 + 各列统计 |
| `GET /api/synthetic/generators` | 已注册的生成器 + 参数 JSON schema |
| `POST /api/synthetic/generate` | 执行一个 `GenerationRequest` → 已注册数据集的摘要（201） |
| `GET /api/scenarios?pack=warehouse` | 场景列表（场景包场景 + 用户场景） |
| `GET /api/scenarios/{scenario_id}?pack=&version=` | 规格、生效参数、参数 schema |
| `POST /api/scenarios` | 创建用户自定义场景（`source: user`），按场景包的参数模型校验（201） |
| `GET /api/models?pack=warehouse&kind=forecast` | 场景包的仿真插件（类型 `forecast`、`simulation`） |
| `GET /api/strategies?pack=warehouse` | 策略 + 参数 schema |
| `POST /api/runs` | 执行一次端到端场景运行（Golden Path）→ 运行记录（201） |
| `GET /api/runs` / `GET /api/runs/{run_id}` | 运行列表（最新在前）/ 运行记录 |
| `GET /api/runs/{run_id}/results` | 各策略（变体）的 KPI、辅助指标、标签 |
| `GET /api/runs/{run_id}/timeseries?variant=&table=&column=&filter=key:value` | 结果列的每日序列，对匹配的实体求和 |
| `GET /api/runs/compare?run_ids=a,b` | 跨运行（跨场景）KPI 行：运行 × 变体 |
| `POST /api/intent` *(P1，未实现)* | 自然语言 → 建议的运行请求（经确认前不执行） |

时间序列示例：`variant=dynamic&table=inventory_ledger&column=closing_on_hand&filter=product_id:FOODS_3_090`。

## 3. `POST /api/runs` — 请求

```json
{
  "pack": "warehouse",
  "reference_id": "m5_subset",
  "scenario_id": "high_demand",
  "scenario_version": null,
  "scenario_overrides": {"lead_time_delta": 2},
  "seed": 20260927,
  "horizon_days": 91,
  "options": {
    "forecast_model": "lightgbm",
    "strategies": ["reorder_point", "safety_stock", "dynamic"],
    "warm_up_days": 56,
    "forecast_horizon_days": 56
  }
}
```

- 框架字段是通用的；`options` 由场景包校验（`warehouse`：`forecast_model` ∈ `seasonal_naive` |
  `moving_average` | `lightgbm`、`strategies`、`warm_up_days`、`forecast_horizon_days`）。
- `scenario_overrides` 按场景包的场景参数模型校验并被记录。
- 预测区间从参考数据最后一个观测销售日的次日开始（v0.1 不支持自由指定起始日期）。
- 需求始终为合成需求（基于参考数据校准的时间序列生成器，并应用场景）。回放参考需求（Gate 0 草案中的
  `demand_source = reference`）**NOT IMPLEMENTED**（未实现）。

在内部，服务将该请求体映射为应用层的 `RunRequest`（字段相同，`reference` = `reference_id` 对应的已配置目录）。

## 4. `POST /api/runs` — 响应（节选）

```json
{
  "run_id": "run_20260928_101500_1a2b3c4d",
  "status": "succeeded",
  "pack": "warehouse",
  "pack_version": "0.1.0",
  "request": {"...": "validated request"},
  "scenario": {"scenario_id": "high_demand", "version": "1.0.0", "parameters": {"...": "..."}, "source": "pack"},
  "scenario_overrides": {"lead_time_delta": 2},
  "labels": ["prototype", "synthetic-data"],
  "variant_metrics": {
    "reorder_point": {"fill_rate": 0.912, "stockout_day_rate": 0.061, "ordering_cost": 1650.0, "holding_cost": 184.2, "lost_sales_cost": 1286.3, "total_cost": 3120.5, "...": "..."},
    "safety_stock":  {"fill_rate": 0.957, "...": "..."},
    "dynamic":       {"fill_rate": 0.968, "...": "..."}
  },
  "supporting_metrics": {"forecast": {"wape": 0.41, "...": "..."}},
  "inputs":  {"synthetic_demand": {"dataset_id": "...", "version": "1", "content_hash": "sha256:..."}, "...": "..."},
  "outputs": {"dynamic.inventory_ledger": {"dataset_id": "...", "version": "1", "content_hash": "sha256:..."}, "...": "..."},
  "created_at": "...", "finished_at": "...", "error": null
}
```

（数值仅作示意。）

## 5. 分层

API 路由（router）保持轻薄：校验请求模型 → 调用 `industrial_ai.application.ApplicationService`
→ 返回其读取模型。`api/` 中不包含任何算法或数据处理逻辑，且 `api/` 只导入 `core` 和 `application`
（由架构测试保证）。应用层调用合成数据 API（Synthetic Data API）和仿真 API（Simulation API），
仅负责编排（orchestration）。
