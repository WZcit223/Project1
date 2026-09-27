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

## 6. Initial generators (v0.1 — exactly three)

### 6.1 `rule_based` v1.0.0
Deterministic or rule-driven tables: entity lists, attribute rules (`unit_cost = price × cost_ratio`),
per-row expressions from a small whitelisted rule vocabulary (constant, choice, linear, lookup, derived).
Used for: warehouse, supplier attributes, product-supplier mapping, initial inventory, policies.
No `eval` of arbitrary code.

### 6.2 `statistical` v1.0.0
Sampling from parametric distributions (normal, lognormal, gamma, Poisson, negative binomial,
uniform, categorical) with optional Gaussian-copula correlation between numeric columns.
Used for: lead-time parameters, cost ratios, reliability, case packs.

### 6.3 `time_series` v1.0.0
Count time-series per entity:

```
λ_t = level · trend_t · weekly[dow_t] · yearly[doy_t] · event_t · scenario_t
y_t ~ NegativeBinomial(mean = λ_t, dispersion = φ)       (Poisson if φ → ∞)
```

- **Calibration** (optional, from `reference`): per series estimate level, weekly profile, yearly
  profile, event uplift and dispersion from the reference demand; recorded as a transformation.
- **Scenario effects**: `demand_multiplier`, `seasonality_multiplier` (scales seasonal amplitude
  around 1), shock window (`shock_multiplier` over `[shock_start, shock_start + duration)`), noise scale.
- Output conforms to `retail.sales` + `scenario_id` (`ops.synthetic_demand`).

Explicitly **not** in v0.1: GAN, VAE, diffusion, agent-based, LLM-generated data.

## 7. LLM-assisted generation (P1, reserved)

Allowed shape only: `requirement → LLM → GenerationRequest / scenario proposal (JSON) → schema &
parameter validation → deterministic engine`. The LLM output is recorded in provenance as
`proposal_source="llm"`; the LLM never writes data rows.
