# ADR-002: Registry-based plugin architecture

- Status: Proposed (Gate 0)
- Date: 2026-09-27

## Context
Synthetic generators, simulation models, strategies and (in future) causal models must be selectable,
addable and user-developable without changing core engine code. Every run must record exactly which
plugin versions produced it.

## Decision
- Each plugin type has a Protocol (structural interface) and a registry built on a generic
  `core.Registry[T]` keyed by `(id, semver version)`.
- Plugins declare a Pydantic `parameter_model`; its JSON schema drives validation and UI forms.
- External packages (scenario packs, user plugins) are discovered through Python **entry points**
  (`industrial_ai.scenario_packs`, `industrial_ai.generators`, `industrial_ai.simulation_plugins`).
- Plugins are deterministic given inputs and seed; version bumps on output-changing behaviour.

## Alternatives
1. Hard-coded if/else dispatch: simple, but every new algorithm edits the core.
2. Abstract base classes with deep inheritance: couples plugins to implementation details.
3. Dynamic loading from file paths / arbitrary code strings: flexible, but unsafe and not reproducible.

## Rationale
Protocols + registries are small, typed and testable; entry points are the standard Python
mechanism and need no extra dependency.

## Consequences
- Contract tests are required for each plugin.
- Plugin ids and versions become part of provenance and the public API.
