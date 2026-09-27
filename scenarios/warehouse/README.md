# Warehouse scenario pack

`industrial-ai-warehouse` — the first validation case of the Industrial AI framework:
**Inventory Demand Forecasting & Replenishment Simulation** (M5 reference demand + synthetic
operational data).

It is a separate package in the uv workspace. It may import `industrial_ai`; the framework
must never import it. See `docs/architecture.md` and `docs/adr/ADR-004-scenario-pack-packaging.md`.
