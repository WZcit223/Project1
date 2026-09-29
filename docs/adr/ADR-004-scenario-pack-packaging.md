# ADR-004: Scenario packs are separate packages in a uv workspace

- Status: Accepted (Gate 0, 2026-09-27)
- Date: 2026-09-27

## Context
The instruction requires that the core never depends on the Warehouse scenario and that new
scenarios can be added without modifying the core. A plain `scenarios/warehouse/` folder is not an
importable Python package, and a sub-package inside `industrial_ai` would make an accidental
dependency easy. The instruction's sketch (§29) listed `simulation/inventory` and `strategies`
inside the core; that conflicts with the higher-priority rule that warehouse-specific logic must not
become core architecture.

## Decision
- `scenarios/warehouse/` is a separate distribution `industrial-ai-warehouse` (import package
  `industrial_ai_warehouse`), a **uv workspace member** depending on `industrial-ai`.
- The core `industrial-ai` package has no dependency on it; the pack registers itself through the
  `industrial_ai.scenario_packs` entry point (ADR-002).
- Inventory simulation, replenishment strategies, the canonical retail model, the M5 adapter, warehouse
  metrics and scenario YAML live in the pack. Generic forecasting and the three synthetic generators
  live in the core.
- The workspace is introduced in Phase 1 (TASK-CORE-001).

## Alternatives
1. `src/industrial_ai/scenarios/warehouse`: simplest, but blurs the boundary.
2. Separate Git repository per pack: strongest isolation, too heavy for v0.1.

## Rationale
Package boundaries make the dependency direction physically enforceable (plus an import test), and
a future `scenarios/maintenance/` is a new workspace member with zero core changes.

## Consequences
- Two `pyproject.toml` files; one shared `uv.lock` at the root.
- Documentation (architecture.md §3) reflects the refined layout.
