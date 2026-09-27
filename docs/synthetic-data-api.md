# Synthetic Data API — v0.1

Status: **Approved at Gate 0 (2026-09-27), v0.1 baseline** · 中文: [zh/synthetic-data-api.md](zh/synthetic-data-api.md)
Package: `industrial_ai.synthetic` · Related: [plugin-spec.md](plugin-spec.md), [ADR-002](adr/ADR-002-plugin-architecture.md)

Interfaces below are **implemented** in `industrial_ai.synthetic` (Phase 4).

## 1. Generator interface

```python
class SyntheticDataGenerator(Protocol):
    generator_id: str                    # e.g. "time_series"
    generator_version: str               # semver, e.g. "1.0.0"
    description: str
    parameter_model: type[BaseModel]     # Pydantic model validating `parameters`
    scenario_parameters: frozenset[str]  # scenario parameters this generator can apply

    def generate(
        self,
        schema: DatasetSchema,
        constraints: ConstraintSet,
        scenario: ScenarioSpec | None,
        seed: int,
        size: GenerationSize,
        parameters: BaseModel,           # instance of parameter_model, validated by the engine
        reference: Dataset | DatasetBundle | None = None,
    ) -> GeneratedData: ...              # data + transformation steps + warnings
```

| Argument | Meaning |
|---|---|
| `schema` | Target schema of the generated table |
| `constraints` | Extra constraints beyond the schema (ranges, relationships, sums), see §3 |
| `scenario` | Scenario whose parameters adjust generation (e.g. `demand_multiplier`); `None` = neutral |
| `seed` | Integer seed; the **only** source of randomness (`numpy.random.default_rng(seed)`) |
| `size` | `GenerationSize(rows=…)` for tables or `(start=…, periods=…)` for daily series; unset fields are derived (e.g. one row per reference row) |
| `parameters` | Generator-specific parameters, validated by `parameter_model` |
| `reference` | Optional reference data used for calibration (e.g. M5 subset) |

Generators return `GeneratedData`, not a dataset: the **engine** computes hashes, provenance and
validation, so a plugin cannot emit data with missing or fabricated provenance.

Rules:
- Generators are **pure** with respect to inputs: no global RNG, no wall-clock dependence, no network.
- Invalid parameters raise `GeneratorParameterError`; constraint violations in output raise
  `ConstraintViolationError` (with the `ValidationReport`). Generators never silently clip or drop
  data unless the clipping rule is an explicit, recorded parameter.
- Scenario parameters a generator does not apply are listed as **warnings** (in the result and in
  provenance), never silently ignored.

## 2. Output: `SyntheticDataset`

```
SyntheticDataset (a Dataset subtype)
├── data, schema, metadata (source_type = "synthetic"), provenance
├── generation_config   GenerationConfig: generator id/version, schema id/version, constraints,
│                       scenario, seed, size, validated parameters (fully serialisable)
├── validation_report   ValidationReport (always passed; failures raise instead)
├── warnings
└── generator_id / generator_version / random_seed   (properties of generation_config)
```

## 3. Constraints

`ConstraintSet` is a list of declarative, serialisable constraints checked by
`industrial_ai.foundation.validation` after generation:

| Constraint | Example |
|---|---|
| `range` | `quantity ≥ 0` |
| `not_null` | `unit_cost` |
| `unique` | primary key |
| `foreign_key` | `product_supplier.supplier_id ∈ supplier.supplier_id` |
| `relation` | `lead_time_std_days ≤ lead_time_mean_days` |
| `integer` | `quantity` is integral |

Validation returns a `ValidationReport` (passed flag, per-constraint results, violating row counts);
it is stored with the dataset metadata.

## 4. Registry and engine

```python
registry = new_generator_registry()                 # core Registry keyed by (generator_id, version)
registry.register(TimeSeriesGenerator())
registry.get("time_series")                          # latest version
describe(registry.get("time_series"))                # GeneratorInfo incl. parameter JSON schema

engine = SyntheticEngine(registry, catalog)          # catalog optional
result = engine.generate(
    GenerationRequest(
        generator_id="time_series",                  # generator_version=None → latest (recorded)
        dataset_id="syn_demand_high", version="1",
        output_schema=SYNTHETIC_DEMAND_SCHEMA,
        constraints=ConstraintSet(...),
        scenario=high_demand,                        # ScenarioSpec or None
        seed=20260927,
        size=GenerationSize(start=date(2016, 1, 1), periods=182),
        parameters={...},
        reference_dataset_id="m5_subset_ca_1_foods_3_top50.sales",   # or pass reference=...
    ),
    register=True,
)
```

The engine: resolves the generator → validates parameters → resolves the reference (argument or
catalog) → calls `generate` → builds the dataset with provenance (inputs pinned by hash, component,
validated parameters, scenario, seed, transformations, warnings) → validates schema + constraints
(failure raises `ConstraintViolationError`) → records the validation in provenance → optionally
registers it in the catalog.

Display ids used in UI and docs: `rule_based_v1`, `statistical_v1`, `time_series_v1`.

## 5. Provenance

Every generated dataset stores a `ProvenanceRecord`:

```json
{
  "artifact_id": "syn_demand_7f3a…",
  "artifact_type": "dataset",
  "created_at": "2026-09-27T10:00:00Z",
  "framework_version": "0.1.0",
  "inputs": [{"dataset_id": "m5_subset_ca1_foods3", "version": "1", "content_hash": "sha256:…"}],
  "component": {"id": "time_series", "version": "1.0.0"},
  "parameters": {"noise_scale": 1.0, "calibration": "per_series_negbin"},
  "scenario": {"scenario_id": "high_demand", "version": "1.0.0", "parameters": {"demand_multiplier": 1.3}},
  "seed": 20260927,
  "transformations": [{"step": "calibrate", "details": {...}}, {"step": "apply_scenario", "details": {...}}],
  "output": {"content_hash": "sha256:…", "row_count": 9100},
  "validation": {"passed": true, "report_id": "…"}
}
```

`component` names the versioned producer — a generator here; an adapter or loader for ingested data. This answers: *source dataset → generator → version → parameters → scenario → seed →
transformations → generated dataset*. A run can be re-executed from its provenance record alone
(given the same source data), and reproduction is verified by comparing `content_hash`.

## 6. Initial generators (v0.1 — exactly three, in `industrial_ai.synthetic.generators`)

### 6.1 `rule_based` v1.0.0
Tables built column by column from a whitelisted rule vocabulary (no code or expressions are
evaluated): `constant`, `sequence` (ids such as `SUP001`), `choice` (optional weights), `uniform`
(int or float), `linear` (`source × scale + offset`), `lookup` (mapping with default) and
`reference_column` (one output row per reference row). Rules may use earlier columns and reference
columns. Used for: warehouse, supplier attributes, product–supplier mapping, initial inventory, policies.

### 6.2 `statistical` v1.0.0
Samples columns from `normal`, `lognormal`, `gamma`, `poisson`, `negative_binomial` (mean,
dispersion), `uniform` and `categorical`; `copy_from_reference` copies id columns row-wise. Optional
**rank correlation** between numeric columns via the Iman–Conover method (marginals preserved exactly,
target correlation achieved approximately; matrix validated as a correlation matrix). Clipping
(`clip_min`/`clip_max`), rounding and integer output are explicit parameters; clipped counts are
recorded in provenance. Used for: lead-time parameters, cost ratios, reliability, case packs.

### 6.3 `time_series` v1.0.0
Daily count series per entity:

```
rate_t   = level · season_t · event_t · level_multiplier · shock_t
season_t = max(0, 1 + seasonality_multiplier · (weekly[dow_t] · monthly[month_t] − 1))
y_t ~ NegativeBinomial(mean = rate_t, dispersion = φ / noise_scale²)   or Poisson(rate_t)
noise_scale = 0 → y_t = round(rate_t)
```

- **Profiles**: explicit `profiles` (level, weekly ×7, monthly ×12, dispersion) or **per-series
  calibration** on a reference history (last `history_window_days`, default 730): level = mean,
  weekly/monthly factors normalised to mean 1, dispersion by method of moments (≈ Poisson when there is
  no over-dispersion). Each series' **leading zeros before its first sale are excluded**. v1 has no
  trend term and no calibrated event uplift (events: explicit `event_dates` × `event_multiplier`).
- **Scenario effects** (generic names): `level_multiplier`, `seasonality_multiplier`, `noise_scale`,
  `shock_multiplier`, `shock_start_day`, `shock_duration_days` (days from the horizon start).
  `scenario_mapping` maps them to a scenario's names, e.g. `{"level_multiplier": "demand_multiplier"}`;
  only effects present in the scenario are applied and reported.
- One independent random stream per series (`SeedSequence(seed).spawn`), rows sorted by time then
  entity. Output: time, entity, value columns plus optional `constant_columns` and
  `scenario_id_column` (e.g. `ops.synthetic_demand`).
- **Known limitation** (observed on the real M5 subset, descriptive only): weekday pattern and scenario
  ratios are reproduced, but runs of zero-sales days in the real data (likely stockouts) are not, so
  synthetic data has fewer zero days.

Explicitly **not** in v0.1: GAN, VAE, diffusion, agent-based, LLM-generated data.

## 7. LLM-assisted generation (P1, reserved)

Allowed shape only: `requirement → LLM → GenerationRequest / scenario proposal (JSON) → schema &
parameter validation → deterministic engine`. The LLM output is recorded in provenance as
`proposal_source="llm"`; the LLM never writes data rows.
