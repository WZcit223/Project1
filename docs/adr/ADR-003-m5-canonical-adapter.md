# ADR-003: M5 enters through an adapter into a canonical model

- Status: Accepted (Gate 0, 2026-09-27)
- Date: 2026-09-27

## Context
M5 (Kaggle) is the reference demand dataset. Its schema is wide (d_1 … d_1941 columns), uses
Walmart-specific identifiers and encodings (e.g. `wday` 1 = Saturday), and is distributed under
competition rules that forbid redistribution. Future scenarios will use entirely different data.

## Decision
- The framework core defines only domain-neutral abstractions (`Dataset`, `DatasetSchema`,
  `DatasetAdapter`).
- The Warehouse pack defines a **canonical retail-demand model** (`retail.*` tables) and an
  **M5 adapter** that converts raw M5 files (or a locally extracted subset) into it.
- No other module reads M5 files. Raw data stays in git-ignored `data/raw/`; attribution metadata
  (source, URL, version, download date, license notes) is recorded on the dataset.
- Tests use a synthetic, M5-shaped fixture; real M5 is optional for local runs.
- The GitHub repository keshusharmamrt/M5-Walmart-Sales-Forecasting is used only as an engineering
  reference, never as a dependency or data source.

## Alternatives
1. Use M5 columns directly throughout: fastest, but couples everything to one dataset.
2. Put the canonical retail model in the core: convenient, but makes the core retail-specific.

## Rationale
An adapter isolates dataset quirks and licensing concerns to one module, keeps the core domain-neutral,
and lets tests run without the real data.

## Consequences
- One extra transformation step (recorded in provenance).
- A subset-extraction script is needed for users (`scripts/make_m5_subset.py`).
