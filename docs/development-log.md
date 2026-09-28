# Development Log

Human-readable record of every meaningful development round (newest first).
Fields: Date · Branch · Objective · Changes · Files / Modules · Tests · Commit · Known Issues · Next.

---

## 2026-09-28 — Phase 16: v0.1.0 release readiness (TASK-DOC-001)

### Branch
`phase16` · Based on: `phase15` at `f620a5e` (Gate 13 APPROVED)

### Objective
Turn the finished system into a credible v0.1.0 prototype release candidate: documentation refresh,
CHANGELOG, technical report, version, regenerated validation report, release checklist. No new
product capability (owner, 2026-09-28).

### Changes
- Spec refresh (EN + ZH): architecture (entry-point registration, real scripts, server-rendered SVG
  charts, plugin ids), scope (BI deferred to P1, V1–V4 wording, three forecast models), requirements
  NFR-8 (V4), demo-guide status.
- Version 0.1.0 in the three workspace packages; `uv lock` (workspace entries only).
- `CHANGELOG.md` (0.1.0, unreleased release candidate).
- Validation report regenerated from clean `47221e4` (0.1.0): 379 of 379 tests categorised; every
  measured value unchanged.
- `docs/technical-report.md` + ZH mirror: what it is, architecture, framework vs scenario, V1–V4,
  what is not demonstrated, limitations, next steps (separate from v0.1 scope).
- `docs/release-checklist.md` with evidence; README status "v0.1.0 release candidate" and links.
- Release checks: fresh clone of `origin/phase16` at `ae8b89d` — `uv sync`, `scripts/demo.py` (output
  identical to the pre-release run) and the browser Golden Path (0 JS errors; baseline, high_demand and
  what-if equal the documented numbers); clone stays clean. Secrets / data scan clean.

### Files / Modules
`docs/{architecture,scope,requirements,demo-guide,technical-report,release-checklist,task-backlog,
validation-report,development-log}.md`, `docs/zh/` mirrors, `CHANGELOG.md`, `README.md`,
`pyproject.toml` × 3, `__init__.py` × 3, `uv.lock`.

### Tests
ruff format / check, mypy clean; pytest 379 passed; link check 0 broken. CI on the final commit is
recorded when it reports.

### Commit
`988ba94` docs(spec), `59bf7cd` build (0.1.0), `47221e4` CHANGELOG, `fea1458` validation report,
`ae8b89d` technical report, `a2fb39d` release checklist, this entry.

### Known Issues
- **Blocking, owner action:** GitHub reports `WZcit223/Project1` as **public**; the committed M5 subset
  was approved on the basis that the repository is private (CLAUDE.md §13; Kaggle: do not
  redistribute). Make the repository private (or remove the subset from the repository and its history)
  before release.
- P2 (not blocking, by decision): TASK-P2-LEGEND, TASK-P2-GENFORMS.

### Next
Gate 14 review by the owner. PR `phase16` → `main`, merge and tag `v0.1.0` only on explicit approval.

---

## 2026-09-28 — Gate 13 close-out: Gate 13 APPROVED

### Branch
`phase15` · `phase16` fast-forwarded to the same commit (no Phase 16 work yet)

### Objective
Close out Gate 13 under the owner's review (2026-09-28): confirm CI for `79b02db`, confirm the two
P0/P1 fixes are closed with regression checks, confirm documentation consistency and the newcomer
framing. No new review round.

### Changes
- CI for `79b02db`: green (GitHub Actions run 52 on `phase15`, run 53 on `phase16`).
- First-run reproducibility re-checked: UI default, `scripts/demo.py`, validation report and demo guide
  all use reference `m5_subset`, scenario `baseline` 1.0.0, `seasonal_naive`, seed 20260927, 91 days.
  Found and fixed a latent gap: the UI took its scenario default from list order, so a saved user
  scenario sorting before `baseline` became the default; the form now preselects `baseline`
  (`8e11b0d`). The regression test covers scenario + version (after a user scenario exists), model,
  horizon and seed; the config test pins the default reference.
- Category completeness: `scripts/validation_report.py` checks V1 + V2 + V3 = all collected tests and
  exits 1 otherwise (each test in exactly one category, by marker). No test was added in the close-out
  (379 tests), so the committed report's counts still hold; it is regenerated at the release commit
  in Phase 16.
- Documentation: README, scope, requirements, CLAUDE.md, validation.md, demo guide and report agree —
  `data/reference/m5_subset/` is the committed, owner-approved subset; M5 = store-level observed retail
  sales, not warehouse operational data; zero observed sales ≠ confirmed stockout; V4 not performed.
- Framing: README intro now states the owner's sentence and separates framework / scenario /
  real-world validation (V4 not performed); demo guide §0 states the same (EN + ZH) (`011ec76`).

### Tests
ruff format / check, mypy (164 files) clean; pytest 379 passed. CI on `011ec76`: green (run 55 on
`phase16`; run 54 on `phase15` is the same commit and was still running when this entry was written).

### Commit
`8e11b0d` fix(ui), `011ec76` docs(readme), this entry.

### Known Issues
P2 backlog unchanged: TASK-P2-LEGEND, TASK-P2-GENFORMS.

### Next
**Gate 13 = APPROVED.** Phase 16 — v0.1.0 Release Readiness on `phase16` (CHANGELOG, technical report,
documentation refresh, version bump, validation report regeneration, release checklist). No new
product capability; PR to `main`, merge and tag only on the owner's explicit approval.

---

## 2026-09-28 — Gate 13 Core Review APPROVED (final: CONDITIONAL — pending CI for `79b02db`)

### Branch
`phase15` (CI green on `2fc7e49`, GitHub Actions run 51; CI for the approval-record commit `79b02db`
had not reported when this entry was written — status corrected in the close-out entry above)

### Changes
Gate 13 decision under the owner's review criteria (2026-09-28), all met: Phase 15 CI green; quick start,
`scripts/demo.py` and the browser Golden Path run from a fresh clone; the default UI run, the demo and
the guide reproduce the committed validation report exactly; reference / synthetic / real data semantics
consistent (M5 = store-level observed retail sales, not warehouse operations; zero observed sales ≠
confirmed stockout); V4 not performed; reproducibility information complete (reference id, scenario and
version, forecast model, seed, commit); no P0/P1 open; development log and backlog updated (M15 ✅).
P2 backlog: TASK-P2-LEGEND, TASK-P2-GENFORMS.

### Next
Phase 16 (documentation refresh, CHANGELOG, v0.1.0 release readiness) on `phase16` from `phase15` —
scope proposed to the owner; no new product features.

---

## 2026-09-28 — Gate 13 review items (Phase 15 follow-up)

### Branch
`phase15` (CI green on `1342174`, run 50, before these changes)

### Findings and fixes
- 🔴→fixed **First-run reproducibility:** an untouched Simulation form used LightGBM (first option), so a
  new user's first run differed from the guide (safety stock 87.8 % vs 86.2 % fill rate). The form now
  preselects `seasonal_naive` (pack default, demo, report); `scripts/demo.py` and the report's Golden
  Path send the model explicitly and the demo prints its configuration. Verified from a fresh clone:
  default browser run = guide numbers exactly.
- 🔴→fixed **Validation categories incomplete:** the new `m5_local` demo test fell into no category
  (378 of 379 reported). V3 is now selected by marker (`m5_local` or new `scenario_checks`) and the report
  proves V1 + V2 + V3 = collected tests (379 = 314 + 51 + 14), failing otherwise.
- 🟡→fixed **Documentation contradictions:** README ("never committed" vs. committed subset), scope data
  table and requirements A5 (M5 local only), CLAUDE.md §11 (owner instruction) — all now state the single
  approved subset and which tests use it; demo guide gains "What this is" (framework vs. scenario pack,
  why inventory, the prototype framing), run-from-root note, default-configuration note; the diagram's
  "(validated)" (schema checks) relabelled to avoid confusion with V1–V4.
- 🟡 kept as backlog: chart-legend overlap (TASK-P2-LEGEND), generator forms (TASK-P2-GENFORMS).
- No architecture violations found: `scripts/demo.py` uses only HTTP `/api/...` (in-process app or
  `--api URL`); UI import-boundary test passes; framework never imports the pack.

### Checks
Fresh clone: `uv sync`, `scripts/demo.py` (exit 0, clean tree), `scripts/serve.py` + default browser run.
ruff format, ruff, mypy strict, pytest: 379 passed; links checked. Report regenerated from the clean
tree at `864bb0b` (numbers unchanged).

### Commits
- acabf07 fix(ui): preselect the demo forecast model on the Simulation page
- 68e4ae3 fix(scripts): state the forecast model explicitly in demo and report runs
- 19f51c2 docs(agent): align the test-data rule with the approved V3 tests
- 2feee94 docs(spec): remove contradictions about the committed M5 subset
- a4ad7e8 docs(demo): explain framework vs scenario and the default configuration
- 696b2db fix(scripts): make the V1-V3 categories cover every test exactly once
- 864bb0b docs(spec): define validation category membership by marker (EN + ZH)
- 108e221 docs(validation): regenerate the report with complete category coverage
- docs(plan) / docs(log): backlog P2 items and this entry

### Next
CI green on the final `phase15` commit → Gate 13 decision → Phase 16.

---

## 2026-09-28 — Phase 15: Demo, communication, quick start (TASK-DEMO-001)

### Branch
`phase15` — based on `phase14` @ `75cca60`

### Objective
Answer: *can another person understand the framework, run the Golden Path, reproduce the result, and
understand what has and has not been validated?* No new algorithms or product features.

### Changes
- `docs/demo-guide.md` (+ `docs/zh/demo-guide.md`): quick start; reference vs. synthetic vs. fixture vs.
  (absent) real operational data, with "zero observed sales ≠ confirmed stockout"; 9-step browser demo;
  Golden Path walkthrough; demo scenario and expected outputs; V1–V4 reading; reproduction
  instructions; known limitations.
- `scripts/demo.py`: scripted Golden Path through the Application API only (in-process or `--api URL`):
  baseline, `high_demand`, what-if `lead_time_delta` +5 with pinned scenario version.
- `tests/integration/test_demo.py`: CLI reproducible on the fixture; on the M5 subset the demo reproduces
  the Golden Path rows of the committed validation report, and the guide's expected-output table must
  equal the report (prevents hand-copied drift).
- README: status (Phases 0–14 implemented), pointer to the guide, demo command.

### Decisions / assumptions (for review)
- "Seed data" for the demo = the committed M5 reference subset + seed 20260927; no extra dataset.
- Expected outputs are the validation report's numbers (seasonal-naive forecast, 91 days); the guide
  does not repeat test counts (they change with every test) and points to the report instead.
- The UI's forecast dropdown lists LightGBM first; the guide tells users to pick `seasonal_naive` to
  match the expected outputs (no UI change in this phase).

### Checks (descriptive)
Headless-browser walkthrough of the guide on the M5 subset: all 9 steps work; UI numbers equal the
guide (baseline fill rate 84.7 / 86.2 / 93.8 %; high_demand total cost $70,030 / $62,865 / $39,865);
~20 s of runs; no JS errors; no 4xx/5xx in the server log. `scripts/demo.py` on the subset ≈ 20 s.

### Tests / checks
ruff format, ruff, mypy strict, pytest: 378 passed; links checked.

### Commits
- 7f9d609 feat(scripts): add the scripted Golden Path demo
- 3c05b2d docs(demo): add the demo guide (EN + ZH)
- 7004388 docs(readme): point newcomers to the demo guide and demo script
- 6a2e9ae docs(plan): mark TASK-DEMO-001 done, M15 awaiting review
- docs(log): record Phase 15 demo round (this entry)

### Known issues
- Forecast dropdown default (LightGBM) differs from the demo's seasonal naive (documented; 🟡 P2).
- Chart-legend overlap (🟡 P2, backlog). CLAUDE.md §11 wording vs. m5_local tests (🟡 P2, owner).

### Next
Gate 13 / M15 review → Phase 16 (docs refresh, CHANGELOG, v0.1.0) on `phase16` from `phase15`.

---

## 2026-09-28 — Gate 12 APPROVED

### Branch
`phase14` (CI green on `4fa0dbd`, GitHub Actions run 48)

### Changes
Gate 12 checklist (owner review 2026-09-28), all met:
- Phase 14 implementation complete (TASK-VAL-001); full suite 376 passed locally; CI green on `4fa0dbd`.
- `validation.md` consistent with the implementation (V1–V4, reference-data checks, test data policy).
- `validation-report.md` generated by `scripts/validation_report.py` from the clean tree at `dc940f7`.
- M5 terminology: store-level retail sales = reference demand/sales environment; operational data
  synthetic; zero observed sales ≠ confirmed stockout.
- V4 explicitly not performed; V1–V3 not presented as real-world validation.
- Development log and backlog updated (M14 ✅, EN + ZH); diff reviewed; branch pushed.
Open (🟡 P2, owner decision): CLAUDE.md §11 wording vs. the approved `m5_local` reference tests.

### Next
Phase 15 (demo, communication, quick start; Gate 13) on branch `phase15` from `phase14`.

---

## 2026-09-28 — Gate 12 review items (Phase 14 follow-up)

### Branch
`phase14`

### Changes
Owner Gate 12 review; no redesign, no scope expansion. Items handled:
1. **Zero sales ≠ confirmed stockout.** M5 is observed retail sales without inventory data; zero observed
   sales may be true zero demand, stockouts or other censoring, and the reference cannot distinguish
   them. Wording corrected in `validation.md`, `synthetic-data-api.md` (known limitation), the roadmap
   row (EN + ZH) and the report generator. Facts kept unchanged: means 14.6 vs 18.2, selling-day means
   17.5 vs 18.7, zero series-days 16.3 % vs 2.7 %; no data or threshold changed.
3. **Documentation drift:** `data-model.md` (EN + ZH) said the extracted subset "stays in data/raw/" and
   is validated there — now points to the committed `data/reference/m5_subset/` used by `m5_local`
   (also in CI); `pyproject.toml` marker text corrected. `validation.md` already reflected the approved
   subset, store-level retail sales as the reference environment, and synthetic operational data.
4. **Report provenance:** regenerated by `scripts/validation_report.py` from the clean tree at
   `dc940f7`; header records commit, branch, Python / pandas / numpy / lightgbm versions and seed; test
   counts come from pytest JUnit XML and reference numbers from code; V1–V4 definitions identical to
   `validation.md` §1; V4 not performed. Diff against the previous report: wording, commit and timings
   only.
Found but not changed (🟡 P2, owner decision): CLAUDE.md §11 says tests never use real M5 data, while
the owner-approved `m5_local` (V3) tests read the committed subset (approved at Gate 6 / M7); a wording
update of §11 is proposed in the Gate 12 report.

### Tests / checks
ruff format, ruff, mypy strict, pytest: 376 passed; links checked.

### Commits
- 8fddf05 docs(spec): stop equating zero observed M5 sales with stockouts
- 5d3a24c fix(scripts): describe zero observed sales without implying stockouts
- c7bed76 docs(spec): point m5_local validation at the committed reference subset
- dc940f7 chore(test): correct the m5_local marker description
- b7761c7 docs(validation): regenerate the report with corrected M5 wording
- docs(log): record Gate 12 review items (this entry)

### Next
CI green on the final `phase14` commit → Gate 12 decision.

---

## 2026-09-28 — Phase 14: Validation suite and report (TASK-VAL-001)

### Branch
`phase14` — based on `phase13` @ `c1a1fcc`

### Objective
A reproducible validation suite and `docs/validation-report.md`, keeping the owner's four categories
explicit: V1 software/framework correctness, V2 framework integration / Golden Path, V3 scenario &
reference-data validation, V4 future real operational validation (Gate 12).

### Changes
- `docs/validation.md` restated around V1–V4 (former levels mapped); explicit statement that M5 is
  store-level retail **sales** used as the reference demand/sales environment, **not** warehouse
  operational data (all operational data is synthetic; sales are censored by stockouts); new §4.1
  reference-data checks; test data policy corrected (committed subset in `data/reference/m5_subset/`).
- `scripts/validation_report.py`: runs the V1 / V2 / V3 pytest selections (JUnit counts per module),
  computes V3 reference-data results (canonical + hybrid data checks, descriptive calibration
  comparison, forecast backtest, Golden Path smoke run with a reproducibility re-run), records commit,
  versions and seed, and writes the V4 "not validated" section. Nothing hand-entered; exit 1 on failure.
- `docs/validation-report.md` generated from `81680d9`: V1 314, V2 49, V3 13 tests — all pass (the three
  selections partition the full 376-test suite); reference-data checks 279 passed, 0 failed; baseline
  re-run reproduces identical metrics.
- The first report draft said item levels "carry over" although synthetic mean demand is +25% vs. the
  reference; fixed to state the gap with computed numbers (selling-day means 17.5 vs. 18.7 units; zero
  series-days 16.3% vs. 2.7% — unmodelled zero-sales runs, roadmap P1).
- README links the report and the generator command; unit tests for the report helpers.

### Decisions / assumptions (for review)
- Category assignment by test location: `tests/unit` → V1; `tests/integration` (except `m5_local`),
  `tests/scenario/test_golden_path.py`, `tests/ui` → V2; `tests/scenario/test_warehouse_scenarios.py` and
  the `m5_local` tests → V3.
- Reference-data comparisons (calibration, forecast accuracy, strategy KPIs) are **descriptive** with no
  thresholds; only data checks and test assertions are pass/fail.
- The report is generated, committed, and regenerated per release (not hand-edited); English only
  (the spec `validation.md` is mirrored in Chinese).

### Tests / checks
ruff format, ruff, mypy strict, pytest: 376 passed (V1 314 + V2 49 + V3 13, per the generated report).

### Commits
- aa91797 feat(scripts): add the validation report generator
- 4f67409 docs(spec): restate validation as four explicit categories V1–V4
- 81680d9 fix(scripts): report the synthetic-vs-reference level gap honestly
- 19276f4 docs(validation): add the generated v0.1 validation report
- 498fc37 docs(readme): link the validation report and its generator command
- c89e345 docs(plan): mark TASK-VAL-001 done, M14 awaiting review
- 4786cdc docs(zh): mirror the V1–V4 validation categories
- docs(log): record Phase 14 validation round (this entry)

### Known issues
- Synthetic demand level is +25% above reference sales overall (zero-run gap, documented).
- The report's run time is ~3 minutes (runs the whole suite plus reference runs).

### Next
Gate 12 / M14 review → Phase 15 (demo script and guide, Gate 13) on branch `phase15` from `phase14`.

---

## 2026-09-28 — Gate 11 / M13 approved

### Branch
`phase13` (CI green on `073b0ce`)

### Changes
- Owner: Gate 11 conditional PASS; the five conditions are closed (see the entry below) and CI is green
  on the final Phase 13 commit, so Gate 11 is approved. Kept as decided: separate `industrial_ai_ui`
  package, HTTP-only API access, Jinja2 + HTMX, server-side SVG charts, JSON synthetic-data request,
  default-driven scenario builder, import-boundary test. Chart-legend overlap is P2 backlog.
  M13 ✅ in the backlog (EN + ZH).
- Owner guidance for Phase 14: keep four validation categories explicit — software/framework
  correctness, framework integration / Golden Path, scenario/reference-data validation, future real
  operational validation — and never present M5 as warehouse operational data (it is the reference
  demand/sales environment used together with synthetic operational data).

### Next
Phase 14 (validation suite and report) on branch `phase14` created from `phase13`.

---

## 2026-09-28 — Gate 11 conditions closed (Phase 13 follow-up)

### Branch
`phase13`

### Changes
Owner review: Gate 11 conditional PASS; no redesign. Items closed:
1. CI green for `b834818` (GitHub Actions run 44, success).
2. ADR-005 **Accepted**, with rationale and consequences.
3. `reference_id` is a **reference dataset identifier** (identifier pattern, path-like values → 422);
   run records returned by the API no longer include the server-side location (`request.reference`).
   What-if re-runs now **pin the original scenario version** (before: "latest", so a newer version
   could leak in) and keep reference id, seed, horizon, options and earlier overrides. New API tests for
   path rejection / hiding and re-run semantics; UI test checks the what-if request.
4. Scenario builder and what-if read the parameter schema of the actual scenario from the API (no
   hard-coded `baseline`); a stub-API test renders and submits a made-up pack's schema.
5. Browser smoke test (headless Chromium, M5 subset) found a real bug: UI route names
   `create_scenario` / `generate` resolved to the same-named **API** routes (UI mounted inside the API
   app), so those forms posted to `/api/...`. Fixed by `ui_` route names; regression tests added (they
   fail without the fix). Re-run smoke test: run, what-if, scenario builder, comparison, overview all
   work; strategy order reorder point → safety stock → dynamic; tile label "stockout-day rate"; no JS
   errors, no 4xx/5xx in the server log.

Chart-legend overlap stays in the backlog (P2, owner decision).

### Tests / checks
ruff format, ruff, mypy strict, pytest: 373 passed.

### Commits
- dcc8d64 fix(api): treat reference_id as a dataset identifier, never a path
- 661a235 fix(ui): pin the scenario version on what-if and read schemas via the API
- 0aa2089 docs(adr): accept ADR-005 (UI as a separate HTTP-only package)
- cb3fac8 docs(spec): document reference ids and re-run semantics (EN + ZH)
- 0cdf1dc fix(ui): prefix UI route names so forms never target API routes
- docs(log): record Gate 11 conditions closed (this entry)

### Next
CI green → Gate 11 approved (per owner) → Phase 14 (validation) on `phase14`.

---

## 2026-09-28 — Phase 13: UI (TASK-UI-001 … 003)

### Branch
`phase13` — based on `phase12` @ `557198b`

### Objective
Browser UI for the Operations Manager / Management demo that executes the Golden Path and uses only the
Application API (Gate 11).

### Changes
- New workspace package `ui/` → `industrial_ai_ui` (ADR-005): Jinja2 + HTMX pages, `ApiClient` (httpx2)
  as the only data source, server-side SVG charts, label catalog `messages.py`, vendored htmx 2.0.4
  (0BSD, SHA-256 recorded). Depends on FastAPI / Jinja2 / httpx2 / uvicorn, not on the framework.
- Pages: Overview, Data (+ dataset provenance and preview), Synthetic data (JSON request), Scenario
  builder (form from the parameter schema), Simulation (HTMX progress), Results (KPI table, demand /
  on-hand / unfulfilled-demand charts, what-if re-run), cross-run comparison (scenarios as columns).
- `scripts/serve.py`: API + UI in one process (UI at `/ui`, in-process ASGI transport);
  `python -m industrial_ai_ui` runs the UI alone against an API URL.
- `RunRequest.reference_id` recorded so the UI can re-run a run without server paths.
- Tests `tests/ui/test_ui.py`: AST check "UI imports no framework module", all pages render, Golden Path
  from browser form posts (4 scenarios), HTMX redirect header, what-if, scenario builder (201 / 409 /
  422), errors and failed runs shown, synthetic generation page.
- Docs: ADR-005, ui-spec §1 + §6, architecture layout, CLAUDE.md layout line, README (status + demo
  command), roadmap row (EN + ZH).

### Decisions / assumptions (for review)
- **UI as a separate package** (ADR-005, *Proposed*): makes "UI imports no framework module"
  enforceable; changes the `ui/` layout line in CLAUDE.md and architecture.md.
- **Charts are server-side SVG** instead of a vendored chart library (spec said "one small chart
  library"): no JavaScript chart code, nothing else to vendor.
- **Synthetic data page takes a JSON request**; forms rendered from each generator's schema are FUTURE
  (roadmap). Scenario runs generate their demand themselves, so the demo does not need this page.
- **Scenario builder** starts from the pack defaults (no Normal / High / Shock / Disruption preset
  buttons); existing scenarios are listed and selectable on the Simulation page.
- htmx obtained from the npm registry (the CDN is blocked in this environment); version and checksum
  recorded.

### Visual check (descriptive)
Demo server on the committed M5 subset driven by headless Chromium (Playwright): Simulation → run
(high_demand, LightGBM) → run page with KPI table and three charts; baseline run; comparison of both
runs; Overview. Pages render as intended; values equal the API results (e.g. baseline fill rate 0.847 /
0.878 / 0.936 for reorder point / safety stock / dynamic).

### Tests / checks
ruff format, ruff, mypy strict, pytest: 368 passed.

### Commits
- 5045b7b feat(application): record the reference id a run was started with
- b5dae08 build(ui): add the UI workspace package with vendored htmx
- bb6f55e feat(ui): add dashboard pages over the Application API
- 0e927ff feat(scripts): add a single-process demo server for API and UI
- eb8ec9b test(ui): run the Golden Path from the browser UI (Gate 11)
- 7136a19 docs(adr): add ADR-005 for the UI as a separate API-only package
- 61e4fb9 docs(spec): document the implemented UI and the ui/ package layout
- 8377459 fix(ui): label the overview tile percentage as stockout-day rate
- c377050 docs(zh): mirror UI spec and layout updates
- e75cbbc docs(plan): mark TASK-UI-001..003 done, M13 awaiting review
- docs(log): record Phase 13 UI round (this entry)

### Known issues
- Chart legends can overlap the lines on narrow charts (cosmetic).
- Each page makes several sequential API calls (fine for a single-user demo).
- English UI only (catalog ready for a Chinese version).

### Next
Gate 11 / M13 review → Phase 14 (validation report) on branch `phase14` from `phase13`.

---

## 2026-09-28 — Gate 10 / M12 approved

### Branch
`phase12` (CI green on `ab3bb79`)

### Changes
- Owner approved Gate 10 (API works independently of the UI) and the Phase 12 contract decisions
  (reference ids, `horizon_days`, pack `options`, generic time series, `/api/references`, 500
  `RUN_FAILED` with run id). M12 ✅ in the backlog (EN + ZH).

### Next
Phase 13 (UI) on branch `phase13` created from `phase12`.

---

## 2026-09-28 — Phase 12: Application API (TASK-API-001, TASK-API-002)

### Branch
`phase12` — based on `phase11` @ `a9a94ae`

### Objective
The HTTP Application API as the only client interface, and the full Golden Path through HTTP only
(Gate 10).

### Changes
- Refactor of the run layer for the API: generic `RunRequest.reference` (replaces the warehouse option
  `reference_dir`), `ScenarioPack.requires_reference` and `components()`, `RunFailedError` with the run
  id, scenarios provider in `WorkflowRunner`, `ScenarioSpec.source` (`pack` | `user`).
- `ApplicationService` (application layer): packs, references, datasets (list / detail with provenance /
  preview), generators and HTTP generation, scenarios incl. **user-defined scenarios** (SQLite, validated,
  immutable), components (models / strategies), runs (start, list, record, results, time series,
  compare). Read models in `application.views`; the API imports only `core` and `application`.
- `industrial_ai.api`: routers `catalog.py` and `runs.py`, documented error shape and codes
  (`errors.py`), lazily created service per app (`deps.py`).
- Settings: `reference_dirs` (`IAI_REFERENCE_DIRS`, default `m5_subset`) — clients send reference ids,
  never paths. `.env.example` updated.
- Gate 10 test `tests/integration/test_api_golden_path.py`: discovery endpoints, all 4 scenarios over
  HTTP, results / time series / compare / dataset provenance, user scenario lifecycle, HTTP generation,
  error shape (422 / 404 / 409 / 500 `RUN_FAILED` with the failed run stored).
- Specs: application-api (rewritten to the implemented contract), plugin-spec §3, scenario-spec §2
  (EN + ZH).

### Decisions / assumptions (for review)
- HTTP run body differs from the Gate 0 draft: `reference_id` (configured id) instead of
  `reference_dataset_id`; `horizon_days` instead of `horizon {start_date, days}` (start = day after the
  last observation); pack choices (`forecast_model`, `strategies`, …) inside `options`;
  `demand_source` / `synthetic` removed (reference replay NOT IMPLEMENTED).
- Time series are generic: `variant` + result `table` + `column` + entity `filter` (sum over matching
  entities) instead of the draft's `metric=inventory&strategy=&product=`.
- `GET /api/references` added; dataset list has no `pack` filter and preview no `table` parameter
  (datasets are single tables).
- Run failure → HTTP 500 `RUN_FAILED` with `details.run_id` (the failed run is stored); invalid requests
  → 422 and nothing stored.
- Runs stay synchronous (a demo-subset run takes seconds); no authentication (non-goal, localhost).

### Tests / checks
ruff format, ruff, mypy strict, pytest: 360 passed in 93.28s (0:01:33).

### Commits
- fdc2a6a refactor(application): prepare the run layer for the HTTP API
- 6940b47 feat(core): add configured reference data directories
- 38258a9 feat(application): add the application service facade for the API
- 65053d3 feat(api): add catalog, scenario, component and run endpoints
- d919239 test(api): run the full Golden Path over HTTP only (Gate 10)
- 918c458 docs(spec): document the implemented Application API
- fcccffb docs(zh): mirror Application API spec updates
- 3148ceb docs(plan): mark TASK-API-001/002 done, M12 awaiting review
- docs(log): record Phase 12 Application API round (this entry)

### Known issues
- Every run re-reads the reference directory and re-registers identical tables by hash (reused).
- The API process holds one service per app; concurrent runs are not coordinated (single-user demo).

### Next
Gate 10 / M12 review → Phase 13 (UI: Jinja2 + HTMX over the Application API) on branch `phase13`
from `phase12`.

---

## 2026-09-28 — Gate 9 / M11 approved

### Branch
`phase11` (CI green on `4aa94b1`)

### Changes
- Owner approved Gate 9 (Golden Path works) and the Phase 11 decisions (simplified ScenarioPack
  interface, generic RunRequest with pack options, configured reference ids at the API, explicit
  override recording, reference-demand replay not implemented). M11 ✅ in the backlog (EN + ZH).

### Next
Phase 12 (Application API) on branch `phase12` created from `phase11`.

---

## 2026-09-28 — Phase 11: Golden Path (TASK-GP-001, TASK-GP-002)

### Branch
`phase11` — based on `phase10` @ `5b49c7d`

### Objective
Framework application layer (scenario pack protocol, pack discovery, workflow runner, run store) and the
Golden Path test: fixture → canonical → synthetic → forecast → inventory × 3 strategies × 4 scenarios →
metrics, persisted and reproducible (Gate 9).

### Changes
- `industrial_ai.application`: `RunRequest` (generic fields + pack `options`), `ResolvedRun`,
  `RunRecord` / `RunStatus` / `DatasetLink`; `ScenarioPack` protocol + `PackRunOutput`;
  `discover_packs()` via entry point group `industrial_ai.scenario_packs`; `WorkflowRunner`
  (validation → `pack.run` → persistence; failures stored as `failed` and re-raised); `RunStore`
  (SQLite run records, datasets in the catalog, identical content reused, conflicting content refused).
  Errors `RunRequestError`, `RunNotFoundError`.
- Foundation: `DatasetCatalog.summary()`, public `create_database_engine`.
- Warehouse pack `pack.py` (`WarehousePack`, `WarehouseRunOptions`) registered through the entry point
  in `scenarios/warehouse/pyproject.toml`; synthetic demand gets a run-scoped dataset id.
- Tests: framework runner / store / discovery with a dummy pack (no warehouse code); Golden Path in
  `tests/scenario/test_golden_path.py` (all 4 scenarios × 3 strategies, persisted datasets re-verified,
  provenance from ledger back to scenario demand, reproducible metrics and output hashes, overrides,
  invalid requests rejected before running, failed runs recorded).
- Specs: plugin-spec §3, application-api §3, roadmap (EN + ZH).

### Decisions / assumptions (for review)
- **ScenarioPack interface simplified** from the Gate 0 sketch (`register(registries)` +
  declarative `build_pipeline`) to `scenarios()` + `run(resolved) → PackRunOutput`; the pack runs its
  pipeline through public engine APIs, the framework runner owns validation, ids, logging and
  persistence. A generic step language is deferred to the roadmap (needs a second pack).
- `RunRequest` is generic; domain choices (reference, forecast model, strategies, warm-up) are pack
  `options` validated by the pack. Phase 12 maps the HTTP request of application-api §3 onto it.
- Warehouse reference data is given as `reference_dir` internally; the API will only accept configured
  reference ids (no client file paths). The horizon starts the day after the last observed sale.
- Scenario overrides keep the scenario id/version and are recorded explicitly (`scenario_overrides` +
  effective parameters in the record and in dataset provenance).
- Run ids are timestamp + random suffix; reproducibility is judged on metrics and content hashes.

### Real-subset check (descriptive / smoke-test evidence only; CA_1 / FOODS_3 / top 50, 91 days, one seed)
Through the workflow runner: seasonal-naive results equal the Phase 10 figures exactly (e.g. baseline fill
rate 0.847 / 0.862 / 0.938). With LightGBM: forecast WAPE 0.443–0.499 (warm-up + horizon, on synthetic
horizon demand), baseline fill rate 0.847 / 0.878 / 0.936, total cost 39,248 / 34,789 / 28,763 USD.
≈ 6 s (seasonal naive) / 8 s (LightGBM) per scenario run.

### Tests / checks
ruff format, ruff, mypy strict, pytest: 352 passed.

### Commits
d831ac0 feat(foundation) · b8e71c5 feat(application) · 203501e feat(warehouse) pack · 0175786 test(scenario)
Golden Path · 563b564 docs(spec) · docs(zh) / docs(plan) / docs(log) (this round).

### Known issues
- `demand_source = reference` (replay) is not implemented (marked in application-api).
- Each run re-registers identical reference / operations tables by hash (reused, not duplicated) — fine
  for the demo subset.

### Next
Gate 9 / M11 review → Phase 12 (Application API) on branch `phase12` from `phase11`.

---

## 2026-09-28 — M10 approved

### Branch
`phase10` (CI green on `b92ca46`)

### Changes
- Owner approved M10 (scenario engine) together with the Gate 8 follow-ups and the Phase 10 decisions
  (High Demand check on expected demand, lost-sales cost at full price, metric renames, user-defined
  scenarios deferred). M10 ✅ in the backlog (EN + ZH).

### Next
Phase 11 (Golden Path) on branch `phase11` created from `phase10`.

---

## 2026-09-27 — Phase 10: Gate 8 follow-ups (TASK-STR-004) + scenario engine (TASK-SCN-001/002)

### Branch
`phase10` — based on `phase9` @ `c894578`

### Objective
Close the Gate 8 follow-ups, then build the scenario registry, YAML scenario configuration, the four
warehouse scenarios and the Level-3 scenario tests, keeping scenarios independent of strategies.

### Changes — Gate 8 follow-ups
- **Metrics** separated and renamed: `fill_rate` (β service level; was `service_level`),
  `stockout_days`, `stockout_day_rate`, `fulfilled_units`, `lost_sales_units`, `avg_on_hand_units` /
  `_value`, `purchase_orders`, `units_ordered`, `order_frequency`, `ordering_cost`, `holding_cost`,
  `inventory_cost` (= ordering + holding), `lost_sales_cost` (lost revenue as shortage-penalty proxy),
  `total_cost` (= all three). data-model §6 distinguishes the reported fill rate from the planning
  `target_service_level` (cycle service level used only for z). `order_cost_range` unchanged.
- **No-look-ahead regression test:** demand tripled after day D; forecasts from origins ≤ D, ledger and
  orders through D identical for all strategies, later results differ.
- **Failure-mode tests:** no history / cold start, sparse demand, zero forecasts, one forecast error,
  NaN / inf / negative forecasts, disruption windows between / on / just before review days, orders in
  transit. They found two defects, now fixed:
  - `ForecastView` silently skipped NaN forecasts (pandas sum) → now raises `SimulationInputError`.
  - `disruption_duration_days = 0` ignored `disruption_start_day` → now means "from the start day to
    the horizon end" (unchanged for the default start 0).
- **Docs:** adaptation frequencies as intentional design, inventory-position semantics, cold start as a
  v0.1 limitation (+ roadmap), Gate 8 acceptance statement, real-subset results labelled descriptive.

### Changes — scenario engine
- `industrial_ai.scenario`: `ScenarioRegistry` (per pack, keyed by id + version, validates every spec
  against the pack's parameter model at registration), `load_scenario` / `load_scenarios` /
  `register_directory` (YAML, `safe_load`), `ScenarioValidationError`.
- Dependency added: `pyyaml` (+ `types-pyyaml` dev) — the spec requires YAML; stdlib has no parser.
- Warehouse pack: `WarehouseScenarioParameters` (scenario-spec §3), `definitions/*.yaml` for
  baseline, high_demand, demand_shock, supply_disruption; `builtin_scenarios()`. The YAML files ship in
  the wheel (checked).
- Tests: framework registry / loader (incl. malformed and unsafe YAML), pack definitions, "every
  parameter applied by exactly one plugin", scenarios package imports no strategy / simulation /
  generator code, Level-3 checks in `tests/scenario/` (every scenario × every strategy).

### Decisions / assumptions (for review)
- Metric ids renamed (pre-API, no external consumers yet); lost-sales cost = lost revenue Σ L·p (an
  upper bound; lost margin would be (p − c)·L).
- High Demand Level-3 check measured on **expected** demand (noise_scale = 0): fixture expected ratio
  1.345; the sampled ratio is 1.24 because Poisson noise on small counts does not cancel even with
  common random numbers. The sampled ratio must still exceed 1.15. Threshold not widened.
- The disruption window is judged by order date (in-transit orders keep their lead time).
- `high_demand` drops the no-op `lead_time_delta 0` from the spec table.
- User-defined scenarios (SQLite, `source: user`) deferred to Phase 12–13; no `source` field yet.

### Real-subset check (descriptive / smoke-test evidence only; CA_1 / FOODS_3 / top 50, 91 days, one seed)
Fill rate · total cost (USD) — reorder_point / safety_stock / dynamic:
- baseline: 0.847 · 39,248 / 0.862 · 36,995 / 0.938 · 29,136
- high_demand: 0.743 · 70,030 / 0.769 · 62,865 / 0.899 · 39,865
- demand_shock: 0.743 · 65,611 / 0.779 · 55,316 / 0.832 · 47,913
- supply_disruption: 0.669 · 67,552 / 0.711 · 61,131 / 0.776 · 54,007
Total cost is now dominated by lost-sales cost (valued at full price); ordering cost ≈ 16–21 k, holding
cost < 1.3 k. Not evidence of economic or algorithmic superiority.

### Tests / checks
ruff format, ruff, mypy strict, pytest: 321 passed.

### Commits
5e0f6de metrics · 9e48ef7 no-look-ahead test · e803083 / 6e06a70 fixes · b01915d failure-mode tests ·
904ca92 docs · b669220 docs(zh) · 3d62f0d build(deps) · 4089709 scenario registry · 7310527 warehouse
scenarios · 6ea8550 Level-3 tests · 27c3358 docs(spec) · 8410029 docs(zh) · docs(plan) / docs(log) (this round).

### Known issues
- Sampled scenario ratios on the small fixture carry a few percent of noise (see decision above).
- Lost-sales cost at full price is a proxy; with it, `total_cost` favours high-stock strategies.

### Next
M10 review → Phase 11 (Golden Path) on branch `phase11` from `phase10`.

---

## 2026-09-27 — Gate 8 / M9 approved with follow-ups

### Branch
`phase9` (CI green on `d22aa82`)

### Changes
- Owner approved Gate 8. Acceptance statement: *the framework can execute and fairly compare multiple
  interchangeable replenishment strategies under identical controlled simulation conditions, with
  reproducible results and explicit temporal information boundaries* — **not** that dynamic
  replenishment is economically or operationally superior in the real world.
- Owner decisions: keep `OperationsConfig.order_cost_range` (do not tune costs to improve the demo);
  the different adaptation frequencies of the strategies are intentional and must be documented
  (reorder point = historical baseline, safety stock = fixed initial buffer, dynamic = periodically
  updated target); real-subset results stay labelled descriptive / smoke-test evidence.
- Follow-ups recorded as TASK-STR-004 (cost components, exact service-level definition, inventory
  position semantics, cold-start limitation, direct no-look-ahead regression test, failure-mode tests).
  M9 ✅ in the backlog (EN + ZH).

### Next
Branch `phase10` from `phase9`: TASK-STR-004 follow-ups, then the scenario engine (TASK-SCN-001/002).

---

## 2026-09-27 — Phase 9: Replenishment strategies (TASK-STR-001 … 003)

### Branch
`phase9` — based on `phase8` @ `91861dc`

### Objective
Three replenishment strategies behind the Phase 8 protocol, compared on identical demand via
`engine.compare` (Gate 8).

### Changes
- `reorder_point` 1.0.0 (s, Q) from mean historical demand, no safety stock; `safety_stock` 1.0.0 (s, S)
  from the forecast and forecast-error std, fixed at the horizon start; `dynamic` 1.0.0 periodic
  order-up-to every R days from the latest forecast and recent errors. `builtin_strategies()` registry.
- `derived.demand_timeline` + `build_demand_timeline()`: observed sales followed by the synthetic horizon
  demand — the input of the rolling forecast during a simulation (no look-ahead).
- Gate 8 integration test: fixture → operations → demand → timeline → seasonal-naive forecast with
  56-day warm-up → inventory simulation × 3 strategies.
- Specs: plugin-spec §4, scenario-spec §6, data-model §3, simulation-api status (EN + ZH).

### Decisions / assumptions (for review)
- R = the item's `order_cycle_days` (14) for all three (override `cycle_days`). The dynamic strategy
  orders every R days, not on every daily review, so its order frequency is comparable with A and B.
- σ_e comes from forecast errors before the horizon: the forecast run starts a **warm-up** (56 days)
  before the horizon and needs `forecast_horizon_days` ≥ reforecast interval + L̄ + R (56 used).
  Missing warm-up or coverage raises an error rather than falling back silently.
- B's levels are set at the first review (horizon start) because `ItemContext` has no date; the
  protocol stays unchanged.
- Forecast demand is read from the day after the review (the order cannot serve today's demand);
  μ_f is the mean over ⌈L̄ + R⌉ days, scaled to L̄ + R.
- σ_e scales with √days (independent daily errors); lead-time variability is not in the safety stock
  (textbook formula as specified).
- A with no demand history never orders.

### Real-subset check (descriptive only; CA_1 / FOODS_3 / top 50, 91 days, seed 20260927)
Service level (inventory cost USD) — reorder_point / safety_stock / dynamic:
- baseline: 0.847 (18,361) / 0.862 (19,400) / 0.938 (18,625)
- high_demand ×1.3: 0.750 (20,610) / 0.777 (21,492) / 0.911 (18,742)
- supply_disruption (+7 d, 50 %, days 28–69): 0.669 (19,014) / 0.711 (20,526) / 0.776 (18,369)
The dynamic strategy holds about twice the stock (holding 829 vs 444 USD at baseline); ordering cost
(~18 k USD) still dominates. ≈ 5 s per scenario incl. forecast.

### Tests / checks
ruff format, ruff, mypy strict, pytest: 280 passed (hand-computed rules for each strategy, warm-up and
coverage errors, timeline, Gate 8 comparison, reproducibility, high demand hurts the static strategy more).

### Commits
e863502 feat(warehouse): demand timeline · 3ca286d feat(warehouse): three strategies ·
0021a7e test(warehouse): Gate 8 comparison · 039f239 docs(spec) · docs(zh) / docs(plan) / docs(log) (this round).

### Known issues
- Ordering cost dominates inventory cost (synthetic order cost 20–60 USD vs low FOODS_3 unit costs), so
  "inventory cost" mostly measures order count; consider tuning `OperationsConfig.order_cost_range`
  (owner decision, affects the demo narrative).
- Safety stock B only modestly beats A: its σ_e is estimated at the start and fixed, and the textbook
  formula ignores lead-time variability.

### Next
Gate 8 / M9 review → Phase 10 (scenario engine) on branch `phase10` from `phase9`.

---

## 2026-09-27 — Gate 7 / M8 approved

### Branch
`phase8`

### Changes
- Owner approved Gate 7 (inventory simulation works) and the seven Phase 8 decisions (strategy protocol
  delivered early, CRN pre-sampling, unshipped share lost, duration 0 = whole horizon, capacity reported
  only, lost-sales value at mean price, initial on_order after mean lead time). M8 ✅ in the backlog (EN + ZH).

### Next
Phase 9 (replenishment strategies) on branch `phase9` created from `phase8`.

---

## 2026-09-27 — Phase 8: Inventory simulation + metrics (TASK-INV-001, TASK-INV-002)

### Branch
`phase8` — based on `phase7` @ `57c0bb4`

### Objective
Warehouse inventory simulation plugin (daily, single-echelon, lost sales) with ledger and purchase-order
outputs and the KPI set of data-model §6; Gate 7.

### Changes
- Strategy protocol in `industrial_ai_warehouse.strategies` (`ReplenishmentStrategy.create_policy` →
  `ItemPolicy.order_quantity`, `ItemContext`, `DailyObservation`, `ForecastView` without look-ahead,
  strategy registry). Delivered here because the simulation needs it; the three strategies follow in Phase 9.
- `inventory_simulation` 1.0.0: receive → serve → review → order; case pack / MOQ rounding; sampled lead
  times with late deliveries; supply scenario effects (`lead_time_delta`, `supply_capacity_factor`,
  disruption window, `planner_aware`); outputs `sim.inventory_ledger` and `sim.purchase_order`.
- `inventory_metrics`: all data-model §6 metrics plus per-product service level.
- Specs updated: scenario-spec §5, plugin-spec §4, data-model §4/§6 (EN + ZH).

### Decisions / assumptions (for review)
- Strategy protocol defined in Phase 8 (backlog had it in TASK-STR-001) and changed from the Gate 0 sketch
  (`initialise`/`decide`/`OrderDecision`) to `create_policy`/`order_quantity`; rounding stays in the simulation.
- Lead-time noise, lateness and delays are pre-sampled per item and day (common random numbers), so strategies
  compared on the same seed see the same supply conditions.
- The unshipped share under reduced supply capacity is lost (not back-ordered).
- `disruption_duration_days = 0` means the whole horizon.
- Warehouse capacity is reported as a warning when exceeded, not enforced (v0.1).
- Lost-sales value uses the mean reference price (`derived.product_price`).
- Initial `on_order` (0 by default) would arrive after the mean lead time.

### Real-subset check (descriptive only, not committed as a test)
CA_1 / FOODS_3 / top 50, 91-day synthetic horizon, seed 20260927, temporary test order-up-to strategy
(daily review): level 100 → service 0.668, level 300 → 0.929; supply disruption (+7 days lead time, 50 %
capacity, days 14–41) → 0.574 / 0.879. ≈ 0.7 s per run. Ordering cost (≈ 143 k USD) dwarfs holding cost
(≈ 156 USD), because the test strategy orders almost daily and FOODS_3 unit costs are low.

### Tests / checks
ruff format, ruff, mypy strict, pytest: 265 passed (accounting identities, hand-computed 10-day example,
metric recomputation from the ledger, CRN, scenario effects, Gate 7 pipeline on the fixture).

### Commits
412e62c feat(warehouse): strategy protocol · 0b51933 feat(warehouse): inventory simulation + metrics ·
docs(spec) / docs(zh) / docs(plan) / docs(log) (this round).

### Known issues
- Cost balance of the synthetic operations (order cost 20–60 USD vs. low FOODS_3 unit costs) makes ordering
  cost dominate; review when the Phase 9 strategies with order cycles run on the real subset.
- Capacity not enforced; single echelon; no backorders (by scope).

### Next
Gate 7 / M8 review → Phase 9 on branch `phase9` (from `phase8`): reorder point, safety stock, dynamic
strategies, compared on identical demand via `engine.compare` (Gate 8).

---

## 2026-09-27 — M7 approved

### Branch
`phase7`

### Changes
- Owner approved milestone M7 and the five Phase 7 decisions (native LightGBM API, direct multi-step,
  no price/event features in v1, forecasts beyond the last observation, 4-week seasonal naive).
  M7 ✅ in the backlog (EN + ZH).

### Next
Phase 8 (inventory simulation + metrics) on branch `phase8` created from `phase7`.

---

## 2026-09-27 — Phase 7: Forecast plugins (TASK-FC-001, TASK-FC-002) · M5 subset committed

### Branch
`phase7` — based on `phase6` @ `d82f973`

### Objective
Domain-neutral forecast plugins for the Data → Forecast → Simulation pipeline: one baseline pair and
one practical ML model, rolling-origin, provably without look-ahead.

### Changes
- **M5 subset (owner decision, option B):** real subset committed in `data/reference/m5_subset/`
  (65222ec) with a README on origin and Kaggle terms; CLAUDE.md §13 records the single exception;
  `m5_local` tests read it (and therefore also run in CI).
- `simulation.forecasting.rolling`: rolling origins (every 7 days, 28-day horizon), history strictly
  before each origin, `sim.forecast` output with actuals, MAE / RMSE / WAPE / bias.
- `seasonal_naive` 1.0.0 (mean of last 4 same-weekday values), `moving_average` 1.0.0 (28-day mean),
  `lightgbm` 1.0.0 (global Poisson model trained once before the horizon; native API, deterministic).
- `PluginOutput.details` recorded in provenance (e.g. LightGBM training rows, features, importance).
- simulation-api.md §4 documents the implemented plugins (EN + ZH).

### Decisions / assumptions (for review)
- LightGBM via the native `lgb.train` API: the scikit-learn wrapper would add scikit-learn.
  `lightgbm` brings `scipy` as a transitive dependency.
- Direct multi-step LightGBM (horizon day as a feature) instead of recursive prediction: no error
  feedback loop, simpler no-look-ahead guarantee.
- v1 features have no price or event inputs (kept domain-neutral); candidates for a later version.
- Forecasts beyond the last observed date are produced (needed for lead-time planning near the horizon
  end) and have `actual = null`.
- Seasonal naive default averages 4 weeks (N = 1 is the textbook version; 4 is more robust).

### Real-subset check (m5_local test)
50 series, 26 weekly origins, 2015-11-23 … 2016-05-22: WAPE seasonal naive 0.443, moving average 0.459,
LightGBM 0.413 (bias +0.8 %). LightGBM run ≈ 2 s (141,400 training rows). Descriptive only.

### Tests / checks
ruff, mypy strict, pytest: 248 (incl. no-look-ahead tests for all three plugins).

### Commits
65222ec M5 subset, 45c4182 forecast plugins, aaffb3c real-subset forecast test, + docs commits.

### Known issues
- The input to forecasting during a scenario run (history + observed synthetic horizon demand) is
  assembled by the application pipeline (Phase 11); plugins take any observed series.

### Next
Owner review of M7 → Phase 8 (inventory simulation + metrics) on `phase8` from `phase7`.

---

## 2026-09-27 — Gate 6 approved

### Branch
`phase6`

### Changes
- Owner approved Gate 6 and the four Phase 6 decisions (engine-only datasets/provenance, no failed
  result objects, upstream by name, constraints passed to plugins). M6 ✅ in the backlog (EN + ZH).
- Owner chose option B for the real M5 subset (commit it; the repository will be made private later)
  and explicitly accepted that it is publicly visible until then. Implemented on `phase7`.

### Next
Phase 7 (forecast plugins) on branch `phase7` created from `phase6`.

---

## 2026-09-27 — Phase 6: Simulation Engine (TASK-SIM-001)

### Branch
`phase6` — based on `phase5` @ `c16d16c`

### Objective
Gate 6: the simulation engine executes registered plugins, composes them through upstream results
and compares variants — with provenance, validation and no fake results.

### Changes
- `industrial_ai.simulation`: `SimulationPlugin` protocol, `PluginKind` (optimization / causal
  reserved), `RunContext` (horizon, seed, named upstream), `PluginOutput` / `OutputTable`, `Metric`,
  `SimulationResult`, `RunMetadata`, registry (`describe`, `plugins_of_kind`), `SimulationEngine.run()`
  and `.compare()` → `ComparisonResult.metrics_table()`.
- simulation-api.md §1–3 describe the implemented interfaces (EN + ZH).

### Decisions / assumptions (for review)
- Plugins return `PluginOutput`; only the engine builds datasets, provenance and metadata (same pattern
  as synthetic generators).
- No `failed` status objects: every failure raises; `status` is always `succeeded`. (The Gate 0 sketch
  mentioned "succeeded or failed".)
- Upstream results are passed by name in the `RunContext`; their tables become provenance inputs of
  downstream outputs.
- Output tables are validated against their schemas; the run's `constraints` are passed to the plugin
  (e.g. for capacity rules) rather than applied to outputs.
- `compare()` uses the same seed for all variants (common random numbers).

### Tests / checks
ruff, mypy strict, pytest: 231 passed locally (incl. `m5_local`); 8 new engine tests with a dummy
forecast and a dummy stock simulation.

### Commits
73c4311 simulation engine, + docs commit.

### Next
Owner review of Gate 6 → Phase 7 (forecast plugins: seasonal naive, moving average, LightGBM) on
`phase7` from `phase6`.

---

## 2026-09-27 — Gate 5 approved

### Branch
`phase5`

### Changes
- Owner approved Gate 5 and the five Phase 5 decisions (supplier / lead-time split,
  strategy-independent policy settings, no `as_of_date`, operational defaults as assumptions, common
  random numbers). M5 ✅ in the backlog (EN + ZH).
- Owner asked whether the real M5 subset can be pushed to GitHub. Not done: the repository is public
  and the data is under Kaggle competition rules (no redistribution; CLAUDE.md §13). Options put to
  the owner for decision.

### Next
Phase 6 (Simulation Engine) on branch `phase6` created from `phase5`.

---

## 2026-09-27 — Phase 5: Synthetic warehouse data (TASK-WH-001)

### Branch
`phase5` — based on `phase4` @ `4e74edf`

### Objective
Gate 5: warehouse operational data can be generated — reproducibly, validated, with provenance —
completing the Hybrid Validation Environment (real M5 demand + synthetic operations).

### Changes
- `industrial_ai.synthetic.generators.builtin_registry()` (core helper: the three generators).
- Warehouse schemas (1.0.0): `ops.warehouse`, `ops.supplier`, `ops.supplier_lead_time`,
  `ops.product_supplier`, `ops.initial_inventory`, `ops.replenishment_policy`,
  `ops.synthetic_demand`; derived `product_price`, `store_demand`, `planning_input`.
- `generate_operations(retail, seed, config)`: every `ops.*` table via the engine (rule_based /
  statistical), assumptions in `OperationsConfig`, per-table derived seeds, lineage with config and seed;
  `build_hybrid_bundle()`.
- `generate_synthetic_demand(retail, DemandConfig, seed, scenario)`: calibrated time series with
  `demand_multiplier → level_multiplier`, common random numbers across scenarios.
- data-model.md §3 rewritten for the implemented tables and rules (EN + ZH).

### Decisions / assumptions (for review)
- Supplier lead-time parameters split into `ops.supplier_lead_time` (statistical) from `ops.supplier`
  (rule_based), so each table has one generator and a complete provenance chain.
- `ops.replenishment_policy` holds strategy-independent settings (review period 1 day, order cycle
  14 days, target service level 0.95); strategies derive reorder points etc. at run time (Phase 9).
  Replaces the earlier `(…, strategy_id)` + JSON parameters sketch.
- `as_of_date` dropped from `ops.initial_inventory`: the initial state is by definition at the
  simulation start.
- Derived tables (`derived.*`) are explicit datasets with provenance rather than hidden computations.
- Operational defaults (5 suppliers, lead time mean ≈ 6.3 d, cost ratio 0.7, holding 25 %/yr,
  capacity 60 days of demand, initial stock μ·(L̄ + 7)) are illustrative assumptions, not facts.
- Common random numbers for scenario demand (same seed stream for all scenarios).

### Real-subset check (local, not committed)
Operations for `m5_subset_ca_1_foods_3_top50` generated in 0.3 s; hybrid bundle 194 checks,
0 failed, 0 skipped. 1 warehouse (CA_1, capacity 43,879 units); supplier mean lead times 4.5–9.7 days;
unit costs 0.14–3.49 USD; products per supplier 10/8/13/5/14; initial on-hand 10,066 units
(13.8 days of demand).

### Tests / checks
ruff, mypy strict, pytest: 223 passed locally (incl. `m5_local`); CI skips `m5_local`.

### Commits
76a3ede builtin_registry, fdabfff operations + demand, + docs commit.

### Known issues
- With the small fixture and negative-binomial noise, the High-Demand demand ratio varies ±6 % around
  1.3 across seeds even with common random numbers; the scenario effect itself is exact (tested with
  noise off). Phase 14 Level-3 checks should use the noise-free rate or a larger horizon/sample.

### Next
Owner review of Gate 5 → Phase 6 (Simulation Engine: protocol, result model, registry, engine) on
`phase6` from `phase5`.

---

## 2026-09-27 — Gate 4 approved

### Branch
`phase4`

### Changes
- Owner approved Gate 4 and the four Phase 4 decisions (engine-only provenance, generic scenario
  effect names with pack mapping, no trend / calibrated event uplift in v1, Iman–Conover correlation).
  M4 ✅ in the backlog (EN + ZH).

### Next
Phase 5 (synthetic warehouse operational data) on branch `phase5` created from `phase4`.

---

## 2026-09-27 — Phase 4: Synthetic Data Engine (TASK-SYN-001 … 005)

### Branch
`phase4` — based on `phase3` @ `93b8062`

### Objective
Gate 4: synthetic data can be generated reproducibly, with full provenance and validation, from a
pluggable engine with exactly three generators.

### Changes
- **SYN-001** `industrial_ai.scenario.ScenarioSpec` (minimal, generic; registry/YAML in Phase 10);
  `synthetic.base`: `SyntheticDataGenerator` protocol, `GenerationSize`, `GeneratedData`,
  `GenerationConfig`, `SyntheticDataset`; generator registry + `describe()`.
- **SYN-002** `SyntheticEngine` + `GenerationRequest`: parameter validation, reference from argument or
  catalog, provenance (inputs pinned by hash, component, parameters, scenario, seed, steps, warnings),
  schema/constraint validation (`ConstraintViolationError` on failure), optional catalog registration.
- **SYN-003** `rule_based` 1.0.0: whitelisted rules (constant, sequence, choice, uniform, linear,
  lookup, reference_column).
- **SYN-004** `statistical` 1.0.0: seven distributions, Iman–Conover rank correlation (no SciPy),
  explicit clipping recorded in provenance.
- **SYN-005** `time_series` 1.0.0: per-series calibration (leading zeros excluded), weekly/monthly
  seasonality, events, negative binomial / Poisson noise, generic scenario effects with
  `scenario_mapping`; one seed stream per series.
- Refactor: generators report `applied_scenario_parameters`; the engine warns about the rest.
- Gate 4 integration test: fixture → adapter → catalog → three generators → registered datasets;
  two independent runs give identical hashes.
- synthetic-data-api.md §1, 2, 4, 6 describe the implemented interfaces (EN + ZH).

### Decisions / assumptions
- Generators return `GeneratedData`; only the engine writes provenance and validation (plugins cannot
  fabricate them). Spec sketch previously had `generate()` return a `SyntheticDataset`.
- Unused scenario parameters are warnings (in the result and in provenance), never silent.
- Time-series scenario effects have generic names; the warehouse pack will map
  `demand_multiplier → level_multiplier` (keeps the core domain-neutral).
- v1 time series: no trend term, no calibrated event uplift (explicit event dates only).
- Rank correlation via Iman–Conover instead of a Gaussian copula with inverse CDFs (avoids SciPy;
  marginals exact, correlation approximate).

### Local check on the real M5 subset (descriptive, not committed)
Calibrated on 50 CA_1 / FOODS_3 series, 182-day horizon: weekday profile real
[0.94, 0.84, 0.82, 0.81, 0.99, 1.25, 1.35] vs synthetic [0.94, 0.85, 0.83, 0.80, 0.98, 1.24, 1.35];
High Demand / baseline total = 1.33 (demand ×1.3 with seasonality ×1.2); mean per item-day 17.4
(synthetic horizon) vs 15.8 (real, last 730 days); share of zero days 3.8 % vs 15.4 % — runs of zeros
in the real data (likely stockouts) are not reproduced. Generation takes about 0.3 s. No
statistical-equivalence claim (Level 4 is out of scope).

### Tests / checks
ruff, mypy strict, pytest: 213 passed locally (incl. `m5_local` on the real subset); in CI the `m5_local` test is skipped.

### Commits
964f511 protocol/registry/engine, 42f8b8a rule_based, 296a919 statistical, c0dee66 applied
scenario parameters, ddea970 time_series, 9e58448 Gate 4 test, + docs commits.

### Known issues
- Zero-run (stockout / intermittency) structure of real demand not modelled; candidate for a later
  generator version or intermittent-demand option (recorded in the roadmap).

### Next
Owner review of Gate 4 → Phase 5 (synthetic warehouse operational data) on `phase5` from `phase4`.

---

## 2026-09-27 — Real M5 subset check · Gate 3 approved

### Branch
`phase3`

### Objective
Confirm the adapter on real M5 data supplied by the owner, and record Gate 3 approval.

### Changes
- Owner ran `scripts/m5_subset_standalone.py` (added in e54be5b: same output as the project script,
  needs only Python ≥ 3.10 + pandas) on the Kaggle files and uploaded the output; it was placed in
  git-ignored `data/raw/m5_subset/` (**not committed**).
- Gate 3 and the four Phase 3 decisions approved by the owner; M3 ✅ in the backlog (EN + ZH).

### Real-data check (`uv run pytest -m m5_local` + profile)
- `SOURCE.json`: `m5_subset_ca_1_foods_3_top50`, reference data, downloaded 2026-09-20, filters
  CA_1 / FOODS_3 / top 50; `calendar.csv` SHA-256 equals the recorded hash of the original file.
- Conversion: all 10 canonical tables; `validate_bundle`: 85 checks, 0 failed, 0 skipped.
- Sales: 50 items × 1,941 days (2011-01-29 … 2016-05-22) = 97,050 rows; 1,580,183 units; no
  negative or missing values. Per-item daily mean 7.8 – 66.4 (median 13.8); share of zero-sale days
  median 20.5 %, max 53.1 %; 11 items have their first sale after 2011-03-01 (late launch).
- Prices: 13,227 weekly rows, 0.20 – 4.98 USD. Calendar 1,969 days (to 2016-06-19), 167 events.

### Known issues / notes for later phases
- Leading zeros before an item's first sale (not yet on sale) must not be treated as zero demand when
  calibrating synthetic demand (Phase 4/5).
- Observed sales remain censored by stockouts (documented limitation).

### Next
Phase 4 (Synthetic Data Engine) on branch `phase4` created from `phase3`.

---

## 2026-09-27 — Phase 3: M5 adapter (TASK-M5-001 … 004)

### Branch
`phase3` — based on `phase2` @ `ec945b5`

### Objective
Gate 3: M5 can be converted to the canonical schema — without real M5 data in the repository.

### Changes
- **M5-001** `industrial_ai_warehouse.schemas.retail`: ten canonical retail schemas (1.0.0) with
  primary/foreign keys, time index and entity keys.
- **M5-002** `adapters.m5.source` (`M5Source` = `SOURCE.json`, `SubsetFilters`, M5 constants) and
  `adapters.m5.fixture` + `scripts/make_m5_fixture.py`: synthetic, M5-layout fixture in
  `tests/fixtures/m5_like/` (2 stores × 2 departments × 6 items × 1,100 days), byte-identical on
  regeneration, labelled `source_type=fixture`.
- **M5-003** `adapters.m5.M5Adapter` (`m5` 1.0.0): unpivot, ISO weekday (cross-checked), event and
  SNAP rows, deterministic sorting, attribution + per-table provenance; bundle validates with no
  failed or skipped checks.
- **M5-004** `adapters.m5.subset` + `scripts/make_m5_subset.py`: streaming subset extraction with
  verbatim values and `SOURCE.json`; optional `pytest -m m5_local` check of `data/raw/m5_subset/`.
- mypy also covers `scripts/`; pytest marker `m5_local` registered.

### Decisions / assumptions
- SNAP flags modelled as long table `retail.calendar_snap` instead of per-state calendar columns
  (keeps the canonical calendar region-agnostic); data-model.md updated (EN + ZH).
- Without `SOURCE.json`, a folder is treated as original Kaggle files (`reference`, id `m5`,
  download date unknown — recorded as such, never invented).
- Canonical tables take `created_at` from `SOURCE.json`, so conversion is fully deterministic.
- Prices are kept only for product/store series present in the sales file.
- The adapter targets subsets; the full 30,490-series unpivot is not supported in v0.1 (memory).
- Subset top-N ranks items by total sales across the selected stores; ties broken by item id.

### Files / Modules
`scenarios/warehouse/src/industrial_ai_warehouse/{schemas,adapters}/`, `scripts/make_m5_fixture.py`,
`scripts/make_m5_subset.py`, `tests/fixtures/m5_like/`, `tests/unit/warehouse/`,
`tests/integration/test_m5_local.py`, `docs/data-model.md` §2, §5 (+ ZH), `README.md`, `pyproject.toml`.

### Tests / checks
ruff format + lint, mypy strict (src, pack, tests, scripts), pytest: 167 passed, 1 skipped
(`m5_local`, no local subset). CI on `phase3`: see Actions.

### Commits
574bd29 retail schemas, b2664c9 fixture + SOURCE.json, 4e6282d M5 adapter, 7ece2c0 subset script,
+ docs(log) for this entry.

### Known issues
- Not yet run on the real M5 subset: needs the owner to run `make_m5_subset.py` and upload / place
  the output in `data/raw/m5_subset/`.
- M5 sales are observed sales (censored by stockouts); documented, not corrected.

### Next
Owner review of Gate 3 (and real-subset upload when convenient) → Phase 4 (Synthetic Data Engine)
on branch `phase4` from `phase3`.

---

## 2026-09-27 — Gate 2 approved

### Branch
`phase2`

### Changes
- Owner approved Gate 2 and the five Phase 2 decisions (hash semantics, provenance `component`,
  `skipped` checks, strict CSV conversion, free-form dataset versions). M2 ✅ in the backlog (EN + ZH).

### Next
Phase 3 (M5 adapter) on branch `phase3` created from `phase2`.

---

## 2026-09-27 — Phase 2: Dataset foundation (TASK-DATA-001 … 005)

### Branch
`phase2` — based on `phase1` @ `82129d9`

### Objective
Gate 2: a dataset can be loaded, validated, registered and reloaded unchanged.

### Changes
- **DATA-003** (done first; the dataset model embeds it) `foundation.provenance`: deterministic
  `content_hash()` (index- and column-order-independent, logical dtype families, row order kept,
  stable across Parquet), `file_hash()`, immutable `ProvenanceRecord` / `Lineage`.
- **DATA-001** `foundation.datasets`: `FieldSpec`, `DatasetSchema`, `SourceInfo`, `DatasetMetadata`,
  `Dataset` (invariants re-checked on construction), `build_dataset()`, `DatasetBundle`.
- **DATA-002** `foundation.validation`: declarative constraints (range, not_null, unique, integer,
  foreign_key, relation), `validate_dataset()` / `validate_bundle()`, reports with
  passed / failed / skipped and offending-row counts.
- **DATA-004** `foundation.catalog.DatasetCatalog`: SQLite (SQLModel) + Parquet; hash verified on
  write and on read; list, preview, bundles.
- **DATA-005** `foundation.ingestion`: `load_table()` for CSV/Parquet with strict type conversion,
  `DatasetAdapter` protocol and adapter registry.
- mypy now also type-checks `tests/` (strict).
- Integration test: file → load → validate → register → fresh catalog → reload, hash unchanged.

### Dependencies added
Runtime: pandas 3, pyarrow, sqlmodel (with numpy, sqlalchemy). Dev: pandas-stubs.

### Decisions / assumptions
- Content hash keeps row order (generators/adapters produce deterministic order) but ignores index,
  column order and physical dtype width.
- Provenance field `component` (not `generator`), since loaders and adapters also produce datasets;
  synthetic-data-api.md example updated (EN + ZH).
- Metadata `entities` made precise as `entity_counts` (distinct values per entity key).
- Validation reports checks that cannot run as `skipped` (visible, not counted as passed).
- Dataset versions are free-form strings; "latest" = most recently registered. Plugin and schema
  versions stay semver.
- Loader rejects unconvertible CSV values instead of coercing them to missing.
- Phase 2 tasks were implemented directly on `phase2` (each a separate commit).

### Files / Modules
`src/industrial_ai/foundation/{provenance,datasets,validation,catalog,ingestion}/`,
`src/industrial_ai/core/errors.py`, `tests/unit/foundation/`, `tests/integration/`,
`docs/data-model.md` §1.3–1.7, `docs/synthetic-data-api.md` §5 (+ ZH), `pyproject.toml`, `uv.lock`.

### Tests / checks
ruff format + lint, mypy strict (src + tests), pytest: 140 passed, including a cross-process
reload test and the Gate 2 integration test. CI green on `phase2`.

### Commits
baa1a7a provenance/hashing, ecb1185 datasets, 8aa8cd0 mypy tests, dce5ee7 validation,
3217f9a catalog, 6ecfb2c ingestion, 4ea4f57 integration test, + docs(log) for this entry.

### Known issues
- `foundation.transformation` and `foundation.entities` are not built yet (not needed until later phases).
- Observed-sales-vs-true-demand limitation of M5 remains documented, not corrected (data-model.md §2).

### Next
Owner review of Gate 2 → Phase 3 (M5 adapter: canonical retail schemas, synthetic M5-shaped
fixture, adapter, subset-extraction script) on branch `phase3` from `phase2`.

---

## 2026-09-27 — Gate 1 approved

### Branch
`phase1`

### Objective
Record the owner's Gate 1 approval and review decisions.

### Changes
- Gate 1 (project starts, tests run) approved; M1 ✅ in the backlog (EN + ZH).
- Phase 1 decisions accepted: tasks on `phase1` directly, explicit layer dependency table,
  `api` limited to `core` + `application`.
- CLAUDE.md §0.1: replies to the owner are always bilingual (English + Chinese).

### Tests / checks
Docs-only change; checks re-run — pass.

### Next
Phase 2 (Dataset foundation) on branch `phase2` created from `phase1`.

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
