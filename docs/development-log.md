# Development Log

Human-readable record of every meaningful development round (newest first).
Fields: Date · Branch · Objective · Changes · Files / Modules · Tests · Commit · Known Issues · Next.

---

## 2026-09-27 — Phase 1: Framework skeleton (TASK-CORE-001 … 006)

### Branch
`phase1` — based on `phase0` @ `0f04972`

### Objective
Make the project start and its tests run (Gate 1): workspace layout, architecture enforcement,
configuration, logging, plugin registry, API skeleton and CI. No domain logic.

### Changes
- **CORE-001** uv workspace: `scenarios/warehouse` is the separate package `industrial-ai-warehouse`
  (ADR-004), installed via the root dev group only; framework layer packages created
  (`core`, `foundation`, `scenario`, `synthetic`, `simulation`, `application`, `api`).
- **CORE-002** `tests/unit/test_architecture.py` statically enforces R1 (no scenario-pack imports in
  the framework) and R2 (per-layer dependency table, now documented in architecture.md §2, EN + ZH).
  Verified to fail on an injected violation.
- **CORE-003** `core.config.Settings` (pydantic-settings, `IAI_*`, `.env`), `load_settings()`,
  `core.logging.configure_logging()` / `get_logger()`, `core.errors`.
- **CORE-004** `core.registry.Registry[T]` keyed by `(id, semver)`, `core.versioning`; plugin-spec
  (EN + ZH) documents the implemented API.
- **CORE-005** FastAPI `create_app()`, `GET /health`, OpenAPI at `/api/openapi.json`,
  `uv run python -m industrial_ai.api`.
- **CORE-006** GitHub Actions CI: `uv sync --locked`, ruff format/lint, mypy, pytest.

### Dependencies added
Runtime: pydantic, pydantic-settings, fastapi, uvicorn. Dev: httpx2 (Starlette TestClient; `httpx`
is deprecated there).

### Decisions / assumptions
- Phase 1 tasks were small, so they were implemented directly on `phase1` as atomic commits rather
  than separate `feature/*` branches.
- The generic `scenario` layer sits between foundation and synthetic/simulation in the dependency
  table (synthetic generators and simulation plugins both receive a `ScenarioSpec`).
- `api` may import only `core` and `application` (strict reading of ADR-001).
- `Registry` takes a key function so each plugin protocol keeps its own id/version attribute names.

### Files / Modules
`pyproject.toml`, `uv.lock`, `.env.example`, `README.md`, `.github/workflows/ci.yml`,
`src/industrial_ai/{core,foundation,scenario,synthetic,simulation,application,api}/`,
`scenarios/warehouse/`, `tests/unit/`, `tests/integration/`, `docs/architecture.md`,
`docs/plugin-spec.md`, `docs/task-backlog.md` (+ ZH mirrors).

### Tests / checks
ruff format + lint, mypy strict (both packages), pytest: 56 passed (unit + integration).
Manual: API started with uvicorn, `GET /health` → `{"status":"ok","version":"0.1.0.dev0"}`.
CI: GitHub Actions run #1 on `phase1` @ 3a1b8e4 — success (https://github.com/WZcit223/Project1/actions/runs/36307244146).

### Commits
7fcb8a9 build(workspace), e7372eb test(architecture), cddf953 feat(core) config/logging,
afc25ed feat(core) registry, 462ee68 feat(api), 3a1b8e4 ci, + docs(log) for this entry.

### Known issues
- `foundation`, `scenario`, `synthetic`, `simulation`, `application` are still empty packages (by design).
- No database yet; `IAI_DATABASE_URL` is used from Phase 2.

### Next
Owner review of Gate 1 → Phase 2 (Dataset foundation, TASK-DATA-001 …) on branch `phase2` from `phase1`.

---

## 2026-09-27 — Gate 0 approved

### Branch
`phase0`

### Objective
Record the project owner's Gate 0 approval of the architecture baseline.

### Changes
- All specs (EN + ZH) marked "Approved at Gate 0 (2026-09-27), v0.1 baseline".
- ADR-001 … ADR-004 status: Accepted.
- Task backlog: M0 ✅, TASK-ARCH-001 approved. README status updated.
- Approval is recorded here, not via a PR: per CLAUDE.md §7 nothing is merged to `main` during work in progress.

### Tests / checks
Docs-only change; ruff, mypy, pytest and link check re-run — pass.

### Next
Phase 1 (Skeleton): branch `phase1` created from `phase0`, starting with TASK-CORE-001.

---

## 2026-09-27 — Branch policy update

### Branch
`phase0` (renamed from `claude/focused-lamport-421rvy`, then from `phase1` so that branch numbers match backlog phase numbers)

### Objective
Adopt the owner's branching policy: one new branch per major round (phase / feature / function),
created from the latest working branch; no merges to `main` while work is in progress.

### Changes
- CLAUDE.md §7 rewritten (stacked `phase<N>` / `feature/<name>` branches, N = backlog phase number,
  so Phase 0 → `phase0`, Phase 1 → `phase1`; `main` updated only at
  owner-chosen milestones, lineage recorded in this log).
- Task backlog (EN + ZH) references updated; TASK-ARCH-001 branch is `phase0`.

### Tests / checks
Docs-only change; ruff, mypy, pytest and link check re-run — pass.

### Next
Gate 0 review, then Phase 1 (TASK-CORE-001 …) on branch `phase1` created from `phase0`.

---

## 2026-09-27 — TASK-ARCH-001 Architecture baseline

### Branch
`phase0` (based on `main` @ `c3a62bc`; originally pushed as the session branch `claude/focused-lamport-421rvy`, renamed to `phase0`)

### Objective
Establish the architecture baseline (Phase 0) for review at Gate 0: project environment, working
rules, specifications, ADRs and task backlog. No application logic.

### Repository state found
- `main` existed with a single "Initial commit" (README only). No Python project, no other branches.

### Changes
- Initialised uv project (`pyproject.toml`, `uv.lock`, Python ≥ 3.11), dev tools pytest / ruff / mypy.
- Added `.gitignore` (data directories, env, caches), `.env.example`, README with doc index.
- Added `CLAUDE.md` master instruction (used instead of `AI-AGENT.md`, as confirmed).
- Added specs: requirements, scope, architecture, data model, Synthetic Data API, Simulation API,
  Application API, plugin spec, scenario spec, UI spec, validation, task backlog, future roadmap.
- Added ADR-001 … ADR-004.
- Added Chinese mirror of the specs in `docs/zh/`.

### Decisions / assumptions (confirmed with user)
- Single-echelon stocking (store = stocking point), lost sales.
- Service level = fill rate; stockout rate = share of item-days with lost sales; inventory cost =
  holding + ordering; lost-sales value reported separately.
- Demo subset default CA_1 × FOODS_3, top 50 items; real M5 stays local (Kaggle rules); tests use
  a synthetic M5-shaped fixture; subset uploaded by the user when needed.
- Docs bilingual: English authoritative (v1), Chinese mirror (v2) in `docs/zh/`.
- Refinement vs instruction §29 (ADR-004): inventory simulation & strategies live in the warehouse
  scenario pack, which is a separate uv workspace package.
- pandas chosen over Polars for v0.1 (one frame library).

### Files / Modules
`pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `.env.example`, `README.md`,
`CLAUDE.md`, `src/industrial_ai/__init__.py`, `tests/unit/test_package.py`, `docs/**`.

### Tests / checks
`uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`, `uv run pytest` — all pass
(1 smoke test). Markdown relative links checked by script.

### Commits
chore(project) ec8f410, docs(agent) 1b5b03f, docs(spec) 60e0ee9 / 99d7f25 / 4b0ccfb,
docs(adr) 3fc3e04, docs(plan) 0060334, docs(zh) ×2, docs(log) (this entry).

### Known issues
- Scenario numeric defaults and Level-3 thresholds are proposals; tune after first Golden Path run.
- Chart library for the UI not yet chosen (Phase 13).
- Network policy of the cloud environment blocks kaggle.com; M5 subset must be supplied by the user.

### Next
Gate 0 review → branch `phase1` created from `phase0` for TASK-CORE-001 (workspace & package skeleton). No merge to `main` during work in progress.
