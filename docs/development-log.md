# Development Log

Human-readable record of every meaningful development round (newest first).
Fields: Date · Branch · Objective · Changes · Files / Modules · Tests · Commit · Known Issues · Next.

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
