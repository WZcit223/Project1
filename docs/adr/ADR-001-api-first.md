# ADR-001: API-first layered architecture

- Status: Accepted (Gate 0, 2026-09-27)
- Date: 2026-09-27

## Context
The framework must outlive its first UI and its first scenario. Management-facing demos tend to couple
UI code directly to models ("UI → Python model"), which makes it impossible to swap the UI (HTMX →
React → mobile) or reuse algorithms in another scenario.

## Decision
Layers communicate only through explicit interfaces: UI → **Application API** (HTTP/JSON) →
application services → **Simulation API** → plugins → **Dataset API** → foundation, with the
**Synthetic Data API** below the foundation. The UI never imports framework Python modules. API
routers contain no business logic.

## Alternatives
1. Streamlit/Dash app calling models directly: fastest demo, but it violates UI independence and
   hides interfaces.
2. Microservices per layer: strong boundaries, but heavy infrastructure (non-goal).

## Rationale
In-process layered modules with an HTTP boundary only at the UI keep the system simple (single
process) while making every boundary explicit and testable. The OpenAPI schema is the contract for
any future client.

## Consequences
- Slightly more code (request/response models, routers) than a direct UI.
- The API can be tested independently of the UI (Gate 10).
- Import-graph tests enforce layering.
