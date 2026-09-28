# Future Roadmap — v0.1

Status: **Living document** · 中文: [zh/future-roadmap.md](zh/future-roadmap.md)

Out-of-scope ideas are recorded here instead of being implemented (see [CLAUDE.md](../CLAUDE.md) §3).
Priority: **P1** after v0.1 Golden Path · **P2** next phase · **P3** long-term.

## 1. Framework features

| Feature | Why useful | Architecture impact | Priority | Dependencies |
|---|---|---|---|---|
| NL intent agent (limited) | Management-friendly "AI" entry point; converts requests into validated run configs | New `application.intent`; no core changes | P1 | Application API, LLM access |
| Lightweight BI (pivot etc.) | Exploratory analysis for operations users | UI only | P1 | Results API |
| Run report export | Share results with management | `application.reporting` | P1 | Golden Path |
| Experiment tracking UI | Compare many runs over time | Uses existing run store | P1 | Run store |
| LLM-assisted generator config | Faster creation of schemas/configs from requirements | Proposal → validator path; provenance `proposal_source` | P2 | Synthetic API |
| Intermittent-demand / zero-run option for `time_series` | Real M5 demand has runs of zero-sales days (often stockouts) that the v1 negative-binomial model does not reproduce (15 % vs 4 % zero days on the real subset) | New generator version or parameter (e.g. zero-inflation, on/off regime); no engine change | P1 | Phase 4 generator, real-subset comparison |
| Cold-start handling for new items | v0.1 strategies never replenish items without sales history (documented limitation) | New strategy parameter or forecast plugin (analogue items, category priors); no engine change | P2 | Product attributes, Phase 9 strategies |
| Advanced generators (Copula+, GAN, VAE, diffusion, agent-based) | Higher-fidelity synthetic data | New generator plugins only | P2 | Real-data validation method |
| Synthetic-vs-real fidelity metrics (Level 4) | Quantify realism, downstream-model utility, privacy | New validation module | P2 | Real / partner data |
| Optimization plugin | Optimal reorder parameters under constraints | `SimulationPlugin kind=optimization` | P2 | Strategy comparison |
| Causal modeling plugin | Intervention / what-if with causal effects | `SimulationPlugin kind=causal` | P2 | Causal graph knowledge, data |
| Knowledge layer / entity graph | Organise domain knowledge across scenarios | Foundation sub-package behind Dataset API | P3 | Use cases |
| Multimodal data (images, documents, sensor waveforms) | Industrial inspection, maintenance logs | Foundation extension | P3 | Scenario need |
| Declarative pipeline steps for packs | Share step logging / partial re-runs across several scenario packs | `ScenarioPack.run` could return or be driven by a step list; runner change only | P2 | A second scenario pack |
| Generator forms in the UI | Non-technical users configure generators without writing JSON | UI only (render forms from the generators' parameter JSON schema) | P1 | Phase 13 UI |
| Async job execution | Long runs, larger datasets | Runs already expose `status` | P2 | Scale needs |
| React / mobile UI | Enterprise UX | Consumes Application API | P3 | Stable API |
| Enterprise IAM, multi-tenant, cloud deploy | Production use | New cross-cutting services | P3 | Productionisation decision |

## 2. Algorithm & data requirements per scenario (towards full capability)

What would be needed to turn each scenario from a framework validation case into a real capability.

### 2.1 Warehouse / Inventory (current validation case)

| Area | v0.1 (prototype) | Needed for full capability |
|---|---|---|
| Demand data | M5 public sales (store level, observed sales) | Company SKU-level demand incl. stockout flags (true demand), promotions, returns |
| Operational data | Synthetic suppliers, lead times, costs, initial inventory | Real supplier master, PO history with actual lead times, cost structure, warehouse capacities, inventory snapshots |
| Forecasting | Seasonal naive + LightGBM | Hierarchical / probabilistic forecasts (quantiles), promotion & price effects, demand censoring correction, intermittent-demand models (Croston/TSB), model monitoring |
| Inventory model | Single-echelon, lost sales, daily | Multi-echelon (DC ↔ stores), backorders/substitution, capacity & shelf-life constraints, MOQ/case packs from reality |
| Policies | Reorder point, safety stock, dynamic order-up-to | Stochastic optimisation / simulation-optimisation of policy parameters, service-level differentiation (ABC/XYZ), RL (research) |
| Synthetic data | Rule, statistical, time-series generators | Fidelity validated against company data; privacy-preserving generators for data sharing |
| Validation | Level 1–3 | Level 4: backtesting on company history, pilot comparison vs current practice |

### 2.2 Predictive Maintenance (candidate scenario 2)

| Area | Needed |
|---|---|
| Reference data | UCI Condition Monitoring of Hydraulic Systems (real multi-sensor test-rig data with component condition labels); later company sensor + maintenance logs |
| Synthetic data | Sensor signal generators (degradation trajectories, fault injection, noise), failure-event generators |
| Algorithms | Anomaly detection, remaining-useful-life estimation, fault classification |
| Simulation | Maintenance policy simulation (run-to-failure, preventive, condition-based), downtime & cost model |
| Framework impact | New scenario pack; possibly multivariate/high-frequency signal support in foundation |

### 2.3 Industrial Energy Management (candidate scenario 3)

| Area | Needed |
|---|---|
| Reference data | UCI ElectricityLoadDiagrams2011–2014 (370 clients, 15-min load); later plant meter data, tariffs, weather |
| Synthetic data | Load-profile generators (weather, production schedule, price scenarios) |
| Algorithms | Load forecasting (reuses core forecasting), peak detection |
| Simulation | Load shifting / peak-shaving strategies, tariff cost simulation |
| Framework impact | New scenario pack; sub-daily time index support |

## 3. Open questions for later phases

- Distribution-centre tier for warehouse (multi-echelon) — confirm need with business.
- Which real company data (if any) can be made available for Level-4 validation, and under what terms.
- Target hosting for the demo (local laptop vs internal server).
