# 任务待办与阶段计划 — v0.1

状态：**已于 Gate 0 批准（2026-09-27），v0.1 基线** · English (authoritative): [../task-backlog.md](../task-backlog.md)

> 本文为英文版的中文镜像 (v2)；如有歧义以英文版为准。

每个任务的规模都足以由编码智能体（coding agent）在一轮内完成（1–5 个原子提交）。分支策略遵循 [CLAUDE.md](../../CLAUDE.md) §7：每个主要轮次（阶段或重要功能）都从最新的工作分支创建新分支（`phase<N>`，N 与下文阶段编号一致，例如 Phase 0 → `phase0`；阶段内功能轮次用 `feature/<name>`）；开发进行期间不合并到 `main`。除非依赖关系允许，否则**一次只做一个
任务**，并按顺序进行。每个任务都继承
[CLAUDE.md](../../CLAUDE.md) 中的规则（测试、文档、开发日志、提交、推送）以及完成定义（Definition of Done）。

任务字段：**目标（Objective）· 输入（Inputs）· 输出 / 文件（Outputs / Files）· 接口（Interfaces）· 验收（Acceptance）· 测试（Tests）· 非目标（Non-goals）**。
方括号中为建议的分支名。

## 里程碑与关卡

| 里程碑 | 阶段 | 关卡（Gate） | 依赖 | 状态 |
|---|---|---|---|---|
| M0 架构规范 | 0 | G0 架构已文档化并获批准 | — | ✅ 已批准 2026-09-27 |
| M1 框架骨架 | 1 | G1 项目可启动、测试可运行 | M0 | ✅ 已批准 2026-09-27 |
| M2 数据集基础 | 2 | G2 数据集可加载并验证 | M1 | ✅ 已批准 2026-09-27 |
| M3 M5 适配器 | 3 | G3 M5 → 规范模型（canonical） | M2 | ✅ 已批准 2026-09-27 |
| M4 合成数据引擎 | 4 | G4 可复现的合成数据 | M2 | ✅ 已批准 2026-09-27 |
| M5 合成仓储数据 | 5 | G5 运营数据已生成 | M3, M4 | ✅ 已批准 2026-09-27 |
| M6 仿真引擎 | 6 | G6 仿真引擎可执行 | M2 | ✅ 已批准 2026-09-27 |
| M7 预测插件 | 7 | （G6/G7 的一部分） | M6 | ✅ 已批准 2026-09-27 |
| M8 库存仿真 | 8 | G7 库存仿真可工作 | M6, M5 | ✅ 已批准 2026-09-27 |
| M9 策略 | 9 | G8 策略可比较 | M8, M7 | ✅ 已批准 2026-09-27（附后续事项 TASK-STR-004） |
| M10 场景引擎 | 10 | （G8/G9 的一部分） | M4, M6 | ✅ 已批准 2026-09-28 |
| M11 Golden Path | 11 | G9 Golden Path 可工作 | M5–M10 | ✅ 已批准 2026-09-28 |
| M12 Application API | 12 | G10 API 可独立于 UI 工作 | M11 | ✅ 已批准 2026-09-28 |
| M13 UI | 13 | G11 UI 可执行 Golden Path | M12 | ✅ 已批准 2026-09-28（条件已关闭） |
| M14 验证 | 14 | G12 验证通过 | M11–M13 | ⬜ |
| M15 演示 | 15 | G13 演示稳定 | M14 | ⬜ |
| M16 文档与发布 | 16 | G14 v0.1.0 发布候选版 | M14 | ⬜ |

## Phase 0 — 架构

### TASK-ARCH-001 — 架构基线  [`phase0`] ✅ 已于 Gate 0 批准（2026-09-27）
目标：uv 项目、CLAUDE.md、`docs/` 中的全部规范、ADR、待办清单、双语镜像。不含应用逻辑。
验收：文档内部一致；`uv run pytest`、`ruff`、`mypy` 通过；已获项目负责人批准（Gate 0）。

## Phase 1 — 骨架

### TASK-CORE-001 — 工作区与包骨架  [`phase1`] ✅
- 目标：创建 uv 工作区（workspace），包含 `scenarios/warehouse` 成员包 `industrial-ai-warehouse`；按照 [architecture.md §3](architecture.md) 创建空的子包。
- 输出：`pyproject.toml`（workspace）、`scenarios/warehouse/pyproject.toml`、`__init__.py` 文件、`scripts/`、`ui/` 占位。
- 验收：`uv sync` 安装两个包；`import industrial_ai_warehouse` 可用。
- 测试：两个包的导入冒烟测试。
- 非目标：任何逻辑。

### TASK-CORE-002 — 架构约束测试  [`phase1`] ✅
- 目标：测试 `industrial_ai` 从不导入 `industrial_ai_warehouse`，且各层只能向下导入（R1、R2）。
- 接口：测试遍历 `src/industrial_ai/**` 的 AST 导入。
- 验收：测试通过；故意构造的错误导入（在测试内的临时文件中）会使其失败。
- 非目标：第三方 import-linter 依赖。

### TASK-CORE-003 — 配置与日志  [`phase1`] ✅
- 目标：`core.config.Settings`（pydantic-settings，`IAI_*` 环境变量，与 `.env.example` 一致）；`core.logging.configure()`。
- 验收：设置可从环境变量和默认值加载；日志行包含 level/logger/message。
- 测试：环境变量覆盖、非法值报错。
- 非目标：远程日志、密钥管理。

### TASK-CORE-004 — 通用注册表与错误  [`phase1`] ✅
- 目标：以 `(id, version)` 为键、支持最新版本查找的 `core.Registry[T]`；`core.errors` 异常层级；semver 解析辅助函数。
- 验收：register/get/list/contains；拒绝重复；`get(id)` 返回最高 semver。
- 测试：覆盖所有行为的单元测试。

### TASK-CORE-005 — FastAPI 应用与健康检查  [`phase1`] ✅
- 目标：`industrial_ai.api.app:create_app()`，`GET /health` → `{"status":"ok","version":…}`；`scripts/run_api.py` / `uv run` 命令。
- 验收：TestClient 返回 200 且响应体正确。  **Gate 1。**
- 非目标：其他端点。

### TASK-CORE-006 — CI 工作流  [`phase1`] ✅
- 目标：GitHub Actions：在 push/PR 时执行 `uv sync --locked`、ruff 格式检查、ruff lint、mypy、pytest。
- 验收：PR 上工作流为绿色。

## Phase 2 — 数据集基础

### TASK-DATA-001 — 数据集模型  [`phase2`] ✅
- 目标：按照 [data-model.md §1](data-model.md) 实现 `FieldSpec`、`DatasetSchema`、`DatasetMetadata`、`Dataset`、`DatasetBundle`。
- 验收：模型可与 JSON 互相序列化；schema JSON 往返一致。
- 测试：构造、校验错误。

### TASK-DATA-002 — Schema 与约束校验  [`phase2`] ✅
- 目标：`foundation.validation.validate(dataset, constraints) → ValidationReport`（类型、空值、范围、允许值、主键唯一性、bundle 内外键）。
- 测试：每种约束类型各一个通过用例和一个失败用例。

### TASK-DATA-003 — 溯源记录与内容哈希  [`phase2`] ✅
- 目标：`ProvenanceRecord` 模型；DataFrame 的确定性 SHA-256（稳定的列顺序、dtype 归一化）。
- 验收：相同数据 → 相同哈希（与行索引无关）；不同数据 → 不同哈希。

### TASK-DATA-004 — 目录与制品存储  [`phase2`] ✅
- 目标：基于 SQLite（SQLModel）的数据集目录（catalog）+ Parquet 制品（artifact）存储；注册、获取、列表、预览。
- 新增依赖：pandas、pyarrow、sqlmodel。
- 验收：注册 → 在新进程中重新加载 → 哈希一致。  **Gate 2。**

### TASK-DATA-005 — 表格加载器与适配器协议  [`phase2`] ✅
- 目标：根据给定 schema 将 CSV/Parquet 加载为 `Dataset`；`DatasetAdapter` 协议 + `AdapterRegistry`。
- 测试：加载夹具 CSV、schema 不匹配报错。

## Phase 3 — M5 适配器（仓储包）

### TASK-M5-001 — 规范零售 schema  [`phase3`] ✅
- 目标：在场景包中按照 [data-model.md §2](data-model.md) 实现 `retail.*` schema。

### TASK-M5-002 — M5 形态的合成夹具  [`phase3`] ✅
- 目标：`scripts/make_m5_fixture.py` 以原始 M5 文件布局将一个小型合成数据集写入 `tests/fixtures/m5_like/`（带 seed，标注为合成）。
- 验收：重复运行生成字节级一致的文件。

### TASK-M5-003 — M5 适配器  [`phase3`] ✅
- 目标：原始 M5（或子集）→ 带归属元数据的规范 `DatasetBundle`；宽表→长表逆透视；星期重新编码；事件转为行。
- 测试：基于夹具：行数、外键有效性、星期映射、无负数量。  **Gate 3。**

### TASK-M5-004 — 子集提取脚本  [`phase3`] ✅
- 目标：`scripts/make_m5_subset.py --stores CA_1 --dept FOODS_3 --top-n 50`，供用户在本地基于完整 Kaggle 文件运行；写入 `data/raw/m5_subset/` + `SOURCE.json`。
- 验收：可在夹具上运行；以流式方式处理大型销售文件，而不将其全部加载到内存。
- 非目标：从 Kaggle 下载。

## Phase 4 — 合成数据引擎

### TASK-SYN-001 — 生成器协议、SyntheticDataset、注册表  [`phase4`] ✅
- 按照 [synthetic-data-api.md §1–4](synthetic-data-api.md)。验收：示例（dummy）生成器可注册并运行；记录 seed；生成溯源信息。

### TASK-SYN-002 — SyntheticEngine 编排  [`phase4`] ✅
- 参数校验 → 生成 → 约束校验 → 哈希 → 溯源 → 目录注册。

### TASK-SYN-003 — 基于规则的生成器  [`phase4`] ✅
### TASK-SYN-004 — 统计生成器  [`phase4`] ✅
### TASK-SYN-005 — 时间序列生成器（+ 校准）  [`phase4`] ✅
- 每项：契约测试（注册、参数、确定性、schema 一致性）。SYN-005 之后为 **Gate 4**。
- 非目标：GAN/VAE/扩散模型/LLM 生成器。

## Phase 5 — 合成仓储数据

### TASK-WH-001 — 运营 schema 与生成配置  [`phase5`] ✅
- 目标：`ops.*` schema 及生成器配置；一个场景包函数，根据参考数据集与 seed 生成完整的混合 bundle（参考数据 + 合成运营数据）。
- 验收：所有外键可解析；层级 2 检查通过；可复现。  **Gate 5。**

## Phase 6–7 — 仿真引擎与预测

### TASK-SIM-001 — 仿真协议、结果模型、注册表、引擎  [`phase6`] ✅
- 按照 [simulation-api.md](simulation-api.md)，包括 `compare()`。使用示例插件达成 **Gate 6**。

### TASK-FC-001 — 基线预测（季节性朴素法、移动平均）  [`phase7`] ✅
### TASK-FC-002 — LightGBM 预测插件  [`phase7`] ✅
- 新增依赖：lightgbm。无前视（look-ahead）泄漏（需测试）。报告准确率指标。非目标：调参。

## Phase 8–9 — 库存仿真与策略（仓储包）

### TASK-INV-001 — 库存仿真插件  [`phase8`] ✅
- 模型按照 [scenario-spec.md §5](scenario-spec.md)；台账（ledger）+ 采购订单（PO）表。
- 测试：会计恒等式；手工计算的 10 天示例。  **Gate 7。**

### TASK-INV-002 — 指标  [`phase8`] ✅
- [data-model.md §6](data-model.md) 中的全部指标；测试由台账重新计算。

### TASK-STR-001 — 策略协议 + 再订货点  [`phase9`] ✅（协议已在 `phase8` 提前交付）
### TASK-STR-002 — 安全库存策略  [`phase9`] ✅
### TASK-STR-003 — 动态补货策略  [`phase9`] ✅
- 验收：通过 `engine.compare` 在相同需求下比较三种策略。  **Gate 8。**
- Gate 8 验收表述（负责人，2026-09-27）：*框架能够在相同的受控仿真条件下执行并公平比较多个可互换的补货策略，
  结果可复现，时间信息边界明确。* 这**并不**表明任何策略在现实中具有经济或运营上的优越性。

### TASK-STR-004 — Gate 8 后续事项  [`phase10`] ✅
- 保持 `OperationsConfig.order_cost_range` 不变（当前成本结构揭示了订货成本占主导）。
- 拆分成本构成和数量指标（订货 / 持有 / 缺货损失成本、总成本、平均在库数量与价值、采购订单数、订货数量、
  满足率、缺货天数、未满足需求）。
- 真实子集结果仅标注为描述性 / 冒烟测试证据。
- 直接的无前视回归测试：修改某决策日之后的需求，该日之前的预测、订单和决策保持不变。
- 精确定义服务水平指标（不含糊地使用"服务水平"）。
- 记录各策略的库存位置语义、有意设计的不同调整频率（A 历史基线 · B 固定的初始缓冲 · C 定期更新的目标），
  以及冷启动（无销售历史）作为 v0.1 的限制。
- 失效模式测试：稀疏 / 零需求、预测误差观测不足、无效预测值、盘点日附近的提前期中断。

## Phase 10 — 场景引擎

### TASK-SCN-001 — ScenarioSpec、注册表、YAML 加载、参数模型  [`phase10`] ✅
### TASK-SCN-002 — 四个仓储场景 + 层级 3 场景测试  [`phase10`] ✅

## Phase 11 — Golden Path

### TASK-GP-001 — ScenarioPack 协议、场景包发现、工作流运行器、运行存储  [`phase11`] ✅
### TASK-GP-002 — Golden Path 测试  [`phase11`] ✅
- 夹具 → 规范模型 → 合成 → 预测 → 库存 × 3 种策略 → 4 个场景 → 指标；可复现。  **Gate 9。**

## Phase 12 — Application API

### TASK-API-001 — 目录、生成器、场景、模型、策略端点  [`phase12`] ✅
### TASK-API-002 — 运行、结果、时间序列、比较端点  [`phase12`] ✅
- 验收：仅通过 HTTP（TestClient）完成完整 Golden Path。  **Gate 10。**

## Phase 13 — UI

### TASK-UI-001 — 布局、概览、数据页面  [`phase13`] ✅
### TASK-UI-002 — 合成数据、场景构建器页面  [`phase13`] ✅
### TASK-UI-003 — 仿真、结果页面（+ what-if 重新运行）  [`phase13`] ✅
- 验收：可从浏览器执行 Golden Path；UI 代码不导入任何框架模块。  **Gate 11。**

## Phase 14–16 — 验证、演示、发布

### TASK-VAL-001 — 验证套件与 `docs/validation-report.md`  [`feature/validation`]  **Gate 12**
### TASK-DEMO-001 — 演示脚本、种子数据、演示指南（`docs/demo-guide.md`）  **Gate 13**
### TASK-DOC-001 — 技术报告、文档更新（EN + ZH）、CHANGELOG、打标签 `v0.1.0`  **Gate 14**

## P1（Golden Path 之后，时间允许时）

- TASK-P1-INTENT：自然语言意图 → 经过校验的 RunRequest（LLM 提案 + 校验器），未经确认绝不执行。
- TASK-P1-BI：基于结果表的轻量级 BI（透视、分组、筛选）。
- TASK-P1-REPORT：可导出的运行报告（Markdown/HTML）。
