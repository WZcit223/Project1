# ADR-005: The UI is a separate package that talks to the Application API over HTTP

- Status: **Accepted** (Gate 11, 2026-09-28; proposed in Phase 13)
- Date: 2026-09-28

## Context
The UI must call only the Application API (CLAUDE.md §2.3, ui-spec §1) and "UI code imports no
framework module" is the Gate 11 acceptance criterion. The original layout listed `ui/` as templates +
static files "served by a thin UI router", without saying where that router lives. A router inside
`industrial_ai.api` would sit in the framework and could call the application layer directly, making the
rule unenforceable.

## Decision
- `ui/` is a separate uv workspace member `industrial-ai-ui` (import package `industrial_ai_ui`) with
  its templates and static assets. It depends on FastAPI, Jinja2, httpx2 and uvicorn — **not** on
  `industrial-ai` or a scenario pack.
- All data comes from the Application API through `industrial_ai_ui.client.ApiClient` (HTTP JSON).
  An AST test fails if any UI module imports `industrial_ai` or `industrial_ai_warehouse`.
- Deployment: `scripts/serve.py` mounts the UI at `/ui` inside the API app and connects the client
  through an in-process ASGI transport (one process, one port for the demo);
  `python -m industrial_ai_ui` runs the UI alone against any API URL.
- Front-end assets are vendored (htmx 2.0.4, 0BSD, checksum recorded); charts are server-side SVG, so
  no chart library and no Node build are needed.

## Alternatives
1. UI router inside `industrial_ai.api`: fewer packages, but the "API only" rule becomes convention.
2. Browser-side JavaScript calling `/api` directly: needs client-side rendering and a JS toolchain
   (a non-goal for v0.1).

## Consequences
- Three workspace members (framework, warehouse pack, UI); one `uv.lock`.
- The UI can be replaced by another client (React, mobile) without backend changes, as ui-spec requires.
- Page requests make several API calls; acceptable for a single-user demo.

## Rationale for acceptance (Gate 11)
- The boundary is enforced, not conventional: an AST test fails on any `industrial_ai*` import in the UI,
  and a stub-API test shows the scenario builder renders whatever parameter schema the API serves.
- The full Golden Path runs from the browser against the real Application API (tests and a headless
  browser smoke test), so the API contract is sufficient for a client.
- Keeping v0.1 simple: Jinja2 + HTMX, server-side SVG charts, JSON synthetic-data request, a scenario
  builder driven by the API's defaults.

## Consequences (accepted)
- New client features must first exist in the Application API; the UI cannot shortcut to the framework.
- Server-side reference locations stay internal: the API exposes only reference ids, and a UI re-run
  (what-if) pins the original run's reference id, scenario version, seed and options.
- The UI package has its own dependency list (FastAPI, Jinja2, httpx2, uvicorn) and version.
