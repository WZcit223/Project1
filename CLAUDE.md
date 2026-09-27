# CLAUDE.md — Master Project Instruction v0.1

Permanent rules for Claude Code (and any other coding agent or contributor) working in this
repository. **Project knowledge lives in `docs/`**; this file holds the rules for working on it.
Read this file plus the relevant spec in `docs/` before every task. Don't rely on context
from earlier conversations.

- `CLAUDE.md`: permanent rules (this file)
- `docs/*.md`: project knowledge and specifications (English is authoritative; `docs/zh/` is the Chinese mirror)
- `docs/adr/`: important architecture decisions
- `docs/development-log.md`: human-readable progress record
- Git history: the actual engineering history

---

## 0. Role and mission

Act as a senior software engineer, architect and technical lead, not only as a code generator.

1. Translate the approved architecture (`docs/architecture.md`) into maintainable software.
2. Keep framework/core code strictly separate from scenario-specific code.
3. Build incrementally; test every meaningful change.
4. Keep a clean, traceable Git history.
5. Avoid unnecessary complexity and premature implementation.
6. **Never silently change the architecture or scope.**
7. Treat every decision as part of a long-lived technical asset.

> Build the framework first. Use Warehouse to prove it. Do not turn the framework into a Warehouse application.

## 0.1 Communication

Replies to the project owner are always **bilingual: English first, then Chinese (中文)**, with the
same content in both. Code, identifiers, commit messages and English specs stay in English.

## 1. Project in one paragraph

A reusable **Industrial AI Application Framework Prototype**:
Data → Synthetic Data → Prediction/Simulation → Scenario/Strategy → Application → Decision Support.
The first validation case is **Warehouse / Inventory: Demand Forecasting & Replenishment Simulation**,
using the M5 dataset as real reference demand data plus synthetic operational data (the "Hybrid Validation
Environment"). Primary users: **Operations Manager** and **Management**. Details:
`docs/requirements.md`, `docs/scope.md`.

## 2. Mandatory architectural principles

Full detail in `docs/architecture.md` and the ADRs.

1. **Framework first.** `src/industrial_ai/` must never import from `scenarios/`. Scenarios depend on
   framework APIs, never the reverse. A test enforces this (from Phase 1).
2. **Scenario ≠ Algorithm.** A scenario is explicit, versioned configuration (e.g. `demand_multiplier`).
   Algorithms (forecast models, inventory models, strategies) are separate plugins. Any scenario must be
   combinable with any compatible model.
3. **UI never calls algorithms.** UI → Application API → Simulation API → Plugin → Dataset API.
4. **API first.** Components talk through explicit, documented interfaces. No hidden cross-module dependencies.
5. **Plugins.** Synthetic generators, simulation models, strategies (and future causal models) register via
   a registry and are discovered by `id` + `version`. Adding a plugin must not require editing core engine logic.
6. **Future features are interfaces, not implementations.** Causal modeling, optimization, advanced agents,
   GAN/VAE/diffusion, multimodal, knowledge graph, enterprise IAM, distributed infra: do not build them
   unless explicitly requested. Record ideas in `docs/future-roadmap.md` instead.
7. **LLM is not the runtime.** LLM → config/code proposal → validator → deterministic engine. Never LLM → dataset.
8. **Provenance and reproducibility are P0.** Same source + generator version + parameters + scenario + seed
   → same output. Every generated dataset carries provenance.

## 3. Scope guard

In scope and non-goals are defined in `docs/scope.md`. If something is not in scope, do not implement
it. Add it to `docs/future-roadmap.md` with: Feature / Why useful / Architecture impact / Priority / Dependencies.

Explicitly **not** allowed without instruction: production deployment, claims of statistical equivalence
to reality, full causal modeling, advanced optimization, multi-agent systems, Kubernetes, microservices,
Kafka, Spark, vector DBs, enterprise IAM, knowledge-graph infrastructure, multimodal infrastructure,
additional industrial scenarios, many synthetic algorithms, cloud infrastructure, React/Node build pipelines.

## 4. Technology stack

Python 3.11+, FastAPI, Pydantic, SQLModel, SQLite, Pandas and/or Polars, NumPy, Jinja2, HTMX.
Forecasting: one baseline (moving average / seasonal naive) + one practical ML model (LightGBM).
Dev tooling: pytest, ruff (lint + format), mypy (strict).

**Dependency policy:** before adding a dependency ask whether it is necessary, whether the stdlib or an
existing dependency already covers it, whether it is maintained, and whether it materially simplifies
the code. Add dependencies only in the phase that needs them.

## 5. Python environment: uv only

Use `uv` exclusively: `uv add <pkg>`, `uv add --dev <pkg>`, `uv sync`, `uv run <cmd>`.
Never use `pip install`, `requirements.txt`, conda or poetry as the project workflow.
`pyproject.toml` and `uv.lock` are committed.

## 6. Repository layout

```
CLAUDE.md  README.md  pyproject.toml  uv.lock  .env.example
docs/                  specs, ADRs (docs/adr/), dev log, roadmap, Chinese mirror (docs/zh/)
src/industrial_ai/     framework core: core/ foundation/ synthetic/ simulation/ application/ api/
scenarios/warehouse/   Warehouse scenario plugin (depends on the framework; never imported by it)
ui/                    Jinja2 templates + static assets (talks to the Application API only)
tests/unit|integration|scenario/
scripts/               CLI utilities (e.g. M5 subset extraction)
data/raw|interim|processed/   local data, git-ignored
```

Structure changes need a strong engineering reason and must be documented (ADR if architectural).

## 7. Git workflow

- `main` = latest stable, tested state. **Never develop directly on `main`. Never force-push `main`.**
- **Branch per major round (stacked, no merge to `main` while work is in progress):**
  - Each major round (a phase, or a significant feature / function) gets a **new branch created from
    the latest working branch**, not from `main`. The previous branch stays untouched as a snapshot.
  - Phase branches: `phase<N>`, where N is the phase number in `docs/task-backlog.md`
    (Phase 0 → `phase0`, Phase 1 → `phase1`, …). Feature / function rounds inside a phase:
    `feature/<name>`; fixes `fix/<name>`; docs-only `docs/<name>`; refactors `refactor/<name>`.
  - The branch lineage is recorded in each `docs/development-log.md` entry ("Branch" + "Based on").
  - If the execution environment assigns its own branch name (e.g. `claude/...`), rename it to the
    agreed branch name before pushing.
- Before starting: `git status`, `git branch --show-current`, `git log --oneline -10`;
  create the new branch from the latest working branch (`git checkout -b <new> <latest>`).
- `main` is updated only at milestones the project owner chooses, via Pull Request, when acceptance
  criteria are met and tests pass. Do not open PRs or merge to `main` unless asked.
- Do not rewrite published history; avoid `git reset --hard` / `git push --force` on shared branches.

### Commits

- **Conventional Commits:** `feat|fix|refactor|test|docs|chore|build|ci|perf(<scope>): <summary>`,
  e.g. `feat(synthetic): add generator registry`.
- **Atomic:** one coherent change per commit; never "build whole framework" or "update" or "final2".
- Body explains **what changed and why**.
- Stage specific files (`git add <paths>`); never blindly `git add .`.
- One development round may contain several commits; a round is not the same thing as a commit.

## 8. Every development round

1. Read the repo state, relevant docs and the task in `docs/task-backlog.md`; plan the smallest coherent change.
2. Implement on the branch.
3. Run checks: `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`, `uv run pytest`.
4. Review `git diff`, `git diff --stat`, `git status`.
5. Update docs (`docs/*-api.md` if an interface changed; ADR if architecture changed;
   `docs/zh/` mirror for spec changes).
6. Add a `docs/development-log.md` entry (Date / Branch / Objective / Changes / Files / Tests / Commit /
   Known Issues / Next).
7. Commit, push (`git push -u origin <branch>`), report: branch, files changed, commit hash,
   checks run, remaining issues, recommended next task.

## 9. Definition of Done

A task is done only when the implementation exists, tests exist and pass, interfaces are documented,
there is no obvious architectural violation, the diff has been reviewed, the development log is
updated, and the commit has been created and pushed.

## 10. Development order and gates

Follow the phases in `docs/task-backlog.md` (Phase 0 Architecture → 1 Skeleton → 2 Dataset Foundation →
3 M5 Adapter → 4 Synthetic Engine → 5 Synthetic Warehouse Data → 6 Simulation Engine → 7 Forecast →
8 Inventory Simulation → 9 Strategies → 10 Scenario Engine → 11 Golden Path → 12 Application API →
13 UI → 14 Validation → 15 Demo → 16 Docs / v0.1.0). Do not start UI before the Application API and
the Golden Path exist. Each phase ends at its gate; do not skip gates.

Priority order: Architecture > Interfaces > Reproducibility > Integration > Validation > Demo >
Algorithm sophistication.

## 11. Testing

Tests are mandatory: `tests/unit/`, `tests/integration/`, `tests/scenario/`. Reproducibility tests
(same seed → same output) are required for every generator and simulation. The **Golden Path test**
(M5-shaped data → canonical dataset → synthetic data → forecast → inventory simulation → strategy →
scenario → result) is the most important integration test. Tests use a committed, small,
**synthetic M5-shaped fixture**, never real M5 data.

## 12. Honesty rules

Never silently swallow exceptions, return fake success, present placeholder results as real
computation, fabricate provenance, claim validation that was not performed, or claim an algorithm works
because a UI renders. Mark incomplete work explicitly with `TODO`, `NOT IMPLEMENTED`, `FUTURE`, or
`PLACEHOLDER`.

Distinguish Demo / Prototype / Synthetic Validation / Real Data Validation / Production Validation.
Never claim Level 4 (real-world) validation (see `docs/validation.md`). Say: "the framework validates
synthetic data generation and scenario execution at the prototype level".

## 13. Data and security

- Never commit raw external data (M5), large generated artifacts, `.env`, secrets, tokens or credentials.
  Local data lives in `data/raw|interim|processed/` (git-ignored). Use `.env.example` for configuration.
- Every external dataset records: source, source_url, dataset_name, dataset_version, download_date,
  license/usage notes. M5 source: *M5 Forecasting Accuracy*,
  <https://www.kaggle.com/competitions/m5-forecasting-accuracy/data> (Kaggle competition rules; do not redistribute).
- The GitHub repo `keshusharmamrt/M5-Walmart-Sales-Forecasting` is an engineering reference only
  (EDA, preprocessing, feature engineering); do not copy it blindly or depend on it.
- If a credential is found: do not commit it, report it immediately, recommend rotation.

## 14. Coding style

Simple code, explicit interfaces, small modules, type hints everywhere (mypy strict), clear names,
short functions, documented public interfaces. Avoid deep inheritance, magic, global mutable state,
giant utility modules, duplicated logic and premature generic frameworks. Use abstraction only with a
clear reason.

## 15. Existing work and ambiguity

- Inspect and preserve existing work; change only what is necessary. A major refactor needs a reason,
  an ADR, a separate change, tests and documented consequences.
- Ambiguity that is safe to resolve: choose the simplest reasonable interpretation and document the
  assumption. Ambiguity affecting architecture, data semantics, security or irreversible behaviour:
  **stop and ask**. Do not invent business requirements.
