# 应用 API（Application API）— v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../application-api.md](../application-api.md) · 相关：[ADR-001](../adr/ADR-001-api-first.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

应用 API 是 UI（以及未来任何 React / 移动端 / 企业级客户端）使用的**唯一**接口。采用 HTTP + JSON，
由 FastAPI 在 `/api` 下提供服务，OpenAPI 模式（schema）位于 `/api/openapi.json`。
各端点将在 Phase 12 最终确定；本文为目标契约（contract）。

## 1. 约定

- 资源 id 为字符串；版本为语义化版本（semver）字符串。
- 长耗时操作（数据生成、运行）在 **v0.1 中为同步执行**（演示子集运行耗时 < 60 秒），但会返回
  带有 `status` 的资源，以便日后改为异步而不破坏客户端兼容性。
- 错误格式：`{"error": {"code": "SCENARIO_NOT_FOUND", "message": "...", "details": {...}}}`，配合 4xx/5xx 状态码。
- 每个运行（run）及生成数据集的响应都包含一个 `provenance`（数据溯源）链接。
- v0.1 不提供身份认证（非目标）；API 默认绑定到 localhost。

## 2. 端点

| 方法与路径 | 用途 |
|---|---|
| `GET /health` | `{"status": "ok", "version": "0.1.0"}` |
| `GET /api/scenario-packs` | 已安装的场景包（scenario pack，例如 `warehouse`）及其描述 |
| `GET /api/datasets` | 数据目录列表（可按 `source_type`、`pack` 过滤） |
| `GET /api/datasets/{dataset_id}` | 元数据、模式、溯源信息 |
| `GET /api/datasets/{dataset_id}/preview?limit=50&table=` | 前若干行 + 汇总统计 |
| `GET /api/synthetic/generators` | 已注册的生成器 + 参数 JSON schema |
| `POST /api/synthetic/generate` | 执行一个 `GenerationRequest` → 生成的数据集资源 |
| `GET /api/scenarios?pack=warehouse` | 场景列表 |
| `GET /api/scenarios/{scenario_id}` | 场景规格 + 参数 schema |
| `POST /api/scenarios` | 创建用户自定义场景（按场景包的参数 schema 进行校验） |
| `GET /api/models?kind=forecast` | 按类型列出已注册的仿真插件 |
| `GET /api/strategies?pack=warehouse` | 已注册的策略 + 参数 schema |
| `POST /api/runs` | 执行一次端到端场景运行（Golden Path，黄金路径） |
| `GET /api/runs` / `GET /api/runs/{run_id}` | 运行列表 / 运行详情（状态、配置、溯源） |
| `GET /api/runs/{run_id}/results` | 各策略的 KPI、对比表 |
| `GET /api/runs/{run_id}/timeseries?metric=inventory&strategy=&product=` | 图表序列 |
| `GET /api/runs/compare?run_ids=a,b` | 跨运行（跨场景）KPI 对比 |
| `POST /api/intent` *(P1)* | 自然语言 → 建议的 `RunRequest`（经确认前不执行） |

## 3. `POST /api/runs` — 请求

```json
{
  "pack": "warehouse",
  "reference_dataset_id": "m5_subset_ca1_foods3",
  "scenario_id": "high_demand",
  "scenario_overrides": {"lead_time_delta": 2},
  "demand_source": "synthetic",
  "synthetic": {"generator_id": "time_series", "parameters": {"noise_scale": 1.0}},
  "forecast_model": "lightgbm",
  "strategies": ["reorder_point", "safety_stock", "dynamic"],
  "horizon": {"start_date": "2015-11-01", "days": 182},
  "seed": 20260927
}
```

`demand_source`：`synthetic`（基于参考数据校准的时间序列生成器，并应用场景）或
`reference`（回放参考需求，并以确定性方式应用场景乘数）。

## 4. `POST /api/runs` — 响应（节选）

```json
{
  "run_id": "run_20260927_0001",
  "status": "succeeded",
  "request": {"...": "echo of the validated request"},
  "scenario": {"scenario_id": "high_demand", "version": "1.0.0", "parameters": {"...": "..."}},
  "results": {
    "strategies": {
      "reorder_point": {"service_level": 0.912, "stockout_rate": 0.061, "inventory_cost": 1834.2, "...": "..."},
      "safety_stock":  {"service_level": 0.957, "...": "..."},
      "dynamic":       {"service_level": 0.968, "...": "..."}
    },
    "forecast": {"model": "lightgbm", "wape": 0.41}
  },
  "labels": ["prototype", "synthetic-data"],
  "provenance_url": "/api/runs/run_20260927_0001#provenance"
}
```

（数值仅作示意。）

## 5. 分层

API 路由（router）保持轻薄：校验请求模型 → 调用 `industrial_ai.application` 服务 → 映射为
响应模型。`api/` 中不包含任何算法或数据处理逻辑。应用层调用合成数据 API（Synthetic Data API）
和仿真 API（Simulation API），仅负责编排（orchestration）。
