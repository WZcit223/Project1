# Release Checklist — v0.1.0

Status: **Gate 14 APPROVED (2026-09-29) — v0.1.0.** Released by merging PR `WZcit223/Project1#1`
(`phase16` → `main`) and tagging the merge commit `v0.1.0`, on the owner's explicit approval
(CLAUDE.md §7). Merge commit `99c5faa` (CI run 65 green); tag `v0.1.0` at `99c5faa` is created with the GitHub Release by
the owner. Evidence: [development-log.md](development-log.md).

Target: *a technically coherent, reproducible, clearly scoped Industrial AI Application Framework
prototype that another technical person can clone, run, inspect and understand without being misled
about the level of real-world validation.*

Evidence was collected on 2026-09-28 against `phase16`. ✅ done with evidence · ⏳ pending.

## Engineering

| Item | Status | Evidence |
|---|---|---|
| Clean working tree | ✅ | `git status` empty after each commit; fresh clone stays clean after demo and browser runs |
| Tests green | ✅ | `uv run pytest`: 379 passed |
| Type check / lint / format green | ✅ | `mypy` (164 files), `ruff check`, `ruff format --check` clean |
| CI green | ✅ | GitHub Actions run 59 green on `9a994ae` (Phase 16 content complete; later commits only record this result) |
| Fresh clone works; `uv sync` works | ✅ | Clone of `origin/phase16` at `ae8b89d`: `uv sync` OK, packages report version 0.1.0 |
| Demo works | ✅ | `scripts/demo.py` in the fresh clone: exit 0; output identical to the pre-release run |
| Browser Golden Path works | ✅ | `scripts/serve.py` in the fresh clone, scripted browser walk (default form → results → high_demand → compare → what-if → data → synthetic): 0 JS errors, no failed requests; `/health` reports 0.1.0 |

## Reproducibility

| Item | Status | Evidence |
|---|---|---|
| Seed recorded | ✅ | 20260927 in demo, report, guide, UI default, run records |
| Dataset identified | ✅ | Reference id `m5_subset` → `data/reference/m5_subset/` (source metadata in `SOURCE.json`; hash-verified) |
| Scenario / version identified | ✅ | `baseline` 1.0.0 and `high_demand` 1.0.0; what-if pins the version |
| Forecast model explicit | ✅ | `seasonal_naive` in demo options, report, guide and UI preselection (regression test) |
| Validation report regenerated | ✅ | `docs/validation-report.md` from clean `47221e4` (version 0.1.0): 379 of 379 tests categorised; all measured values unchanged |
| Demo numbers match report | ✅ | Automated (`tests/integration/test_demo.py`, `m5_local`); fresh-clone demo and browser runs: baseline fill rate 84.7 / 86.2 / 93.8%, total cost $39,248 / $36,995 / $29,136 |

## Architecture

| Item | Status | Evidence |
|---|---|---|
| UI → Application API boundary preserved | ✅ | UI imports no `industrial_ai*` module (AST test); UI calls `/api/*` only |
| Framework does not depend on the warehouse pack | ✅ | Architecture test R1 and layer table (`tests/unit/test_architecture.py`) |
| Scenario remains plugin-like | ✅ | Pack discovered via entry point `industrial_ai.scenario_packs`; scenarios are versioned configuration |
| No accidental framework / scenario coupling | ✅ | Layer import rules enforced; UI holds only display labels and demo defaults |

## Validation

| Item | Status | Evidence |
|---|---|---|
| V1 documented | ✅ | validation.md §1–3, report §1 (314 tests) |
| V2 documented | ✅ | validation.md §2, report §2 (51 tests) |
| V3 documented | ✅ | validation.md §4, report §3 (14 tests + 279 reference checks; comparisons descriptive) |
| V4 explicitly Not Performed | ✅ | validation.md, report, demo guide, README, technical report |
| Synthetic ≠ real-world validation | ✅ | README framing table; technical report §5; UI badge and footer on every page |
| Limitations documented | ✅ | technical report §6; demo guide §8; validation report §4 |

## Documentation

| Item | Status | Evidence |
|---|---|---|
| README current | ✅ | Framing (framework ≠ scenario ≠ real-world validation), v0.1.0 RC status, links |
| Demo guide current | ✅ | Approved at Gate 13; numbers checked by test |
| Architecture current | ✅ | Refreshed for v0.1.0 (entry point, scripts, SVG charts, plugin ids) |
| Scope current | ✅ | BI deferred to P1, V1–V3 / V4, three forecast models |
| Requirements current | ✅ | A5 (committed subset), NFR-8 (V4) |
| CLAUDE.md consistent | ✅ | §11 test-data rule, §13 committed-subset exception |
| CHANGELOG created | ✅ | `CHANGELOG.md` (0.1.0, unreleased) |
| Technical report created | ✅ | `docs/technical-report.md` + `docs/zh/technical-report.md` |

## Data and licensing

| Item | Status | Evidence |
|---|---|---|
| No secrets, tokens, credentials or `.env` committed | ✅ | Pattern scan of tracked files: no matches; only `.env.example` tracked |
| No raw external data except the approved subset | ✅ | Tracked data: `data/reference/m5_subset/` (~0.73 MB, CA_1 / FOODS_3 / top 50) and `.gitkeep` files only |
| Repository visibility matches the M5 approval | ✅ resolved by owner decision | Owner decision (2026-09-28): the repository `WZcit223/Project1` is set to **private**; the approved M5 subset is retained; no history rewrite (CLAUDE.md §13). Not a release blocker. Visibility confirmation is recorded in the development log at release. |

## Owner decisions (not done by the agent)

- [x] Repository visibility: set to private (owner decision, 2026-09-28).
- [x] Approve a pull request `phase16` → `main` (Gate 14, 2026-09-29).
- [x] Approve the tag `v0.1.0` and a GitHub release (Gate 14, 2026-09-29).
