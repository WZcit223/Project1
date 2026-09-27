# Scenario Specification — v0.1

Status: **Approved at Gate 0 (2026-09-27), v0.1 baseline** · 中文: [zh/scenario-spec.md](zh/scenario-spec.md)

## 1. Principle: Scenario ≠ Algorithm

A **scenario** is an explicit, versioned, validated **configuration of the environment** (demand and
supply conditions). It contains no code. **Algorithms** (forecast models, inventory model, strategies)
are separate plugins. Any scenario can be combined with any compatible algorithm:
Scenario A × Model A, Scenario A × Model B, Scenario B × Model A, …

## 2. Generic `ScenarioSpec` (framework)

```yaml
scenario_id: high_demand          # snake_case, unique within a pack
version: 1.0.0
pack: warehouse
title: High Demand
description: Sustained 30% demand increase with stronger seasonality.
parameters: {...}                 # validated by the pack's scenario_parameter_model
tags: [demand]
```

Scenario files live in `scenarios/warehouse/src/industrial_ai_warehouse/scenarios/*.yaml`.
User-defined scenarios (Scenario Builder) are stored in SQLite with the same structure and
`source: user`. Specs are immutable once used by a run; edits create a new version.

## 3. Warehouse scenario parameters

| Parameter | Type | Default | Valid range | Effect |
|---|---|---|---|---|
| `demand_multiplier` | float | 1.00 | 0.10 – 5.00 | Scales expected demand level |
| `seasonality_multiplier` | float | 1.00 | 0.00 – 3.00 | Scales seasonal amplitude around 1 (0 = flat) |
| `noise_scale` | float | 1.00 | 0.00 – 3.00 | Scales demand dispersion |
| `shock_multiplier` | float | 1.00 | 0.00 – 10.00 | Demand factor inside shock window |
| `shock_start_day` | int | 0 | ≥ 0 | Offset from horizon start |
| `shock_duration_days` | int | 0 | ≥ 0 | 0 = no shock |
| `lead_time_delta` | int (days) | 0 | −30 – 60 | Added to supplier mean lead time (result floored at 1) |
| `disruption_start_day` | int | 0 | ≥ 0 | Offset from horizon start |
| `disruption_duration_days` | int | 0 | ≥ 0 | 0 = from `disruption_start_day` to the horizon end (the whole horizon with the default start 0) |
| `supply_capacity_factor` | float | 1.00 | 0.00 – 1.00 | Fraction of each order quantity the supplier ships during the disruption window |
| `planner_aware` | bool | false | — | Whether strategies see the adjusted lead time (true) or the nominal one (false) |

## 4. Initial scenarios (exactly four)

| scenario_id | Parameters (non-default) | Expected behaviour (tested) |
|---|---|---|
| `baseline` | — | Reference behaviour |
| `high_demand` | demand_multiplier 1.30, seasonality_multiplier 1.20, lead_time_delta 0 | Total demand ↑ ≈ 30% vs baseline (same seed) |
| `demand_shock` | shock_multiplier 2.50, shock_start_day 28, shock_duration_days 14 | Demand ↑ only inside the window |
| `supply_disruption` | lead_time_delta +7, disruption_start_day 28, disruption_duration_days 42, supply_capacity_factor 0.50 | Longer realised lead times / partial receipts in window; stockouts ↑ for static strategies |

Numeric values are proposed defaults for v0.1, tunable after the first Golden Path run; any change
bumps the scenario version.

## 5. Inventory simulation model

Implemented by the Warehouse plugin `inventory_simulation` 1.0.0 (`industrial_ai_warehouse.simulation`).
Daily discrete-time, per item (product × warehouse), single-echelon, lost sales. For each day *t* in the
horizon, in order:

1. **Receive** — shipments arriving on *t*: `opening_on_hand_t = closing_on_hand_{t−1} + arrivals_t`.
2. **Demand** — `fulfilled_t = min(opening_on_hand_t, demand_t)`, `lost_sales_t = demand_t − fulfilled_t`
   (lost, not back-ordered).
3. **Close** — `closing_on_hand_t = opening_on_hand_t − fulfilled_t`.
   (Equivalent to *Inventory(t+1) = Inventory(t) + Arrivals(t) − Demand(t)* with the lost-sales floor at 0.)
4. **Review** — every `review_period_days`, the strategy's policy sees `DailyObservation`
   (on hand, on order, inventory position = on hand + on order, today's demand and fulfilment) and returns
   a quantity; the simulation rounds it up to the case pack after applying the supplier's minimum order
   quantity.
5. **Order** — lead time `L = max(1, round(mean + lead_time_delta_t + std · z_t))`; with probability
   `1 − on_time_probability` add 1–3 days (`max_extra_delay_days`); arrival `t + L`; shipped quantity
   `ceil(quantity · supply_capacity_factor_t)`; the unshipped share is lost. `lead_time_delta` and
   `supply_capacity_factor` apply to orders placed inside the disruption window
   `[disruption_start_day, disruption_start_day + disruption_duration_days)`, or from
   `disruption_start_day` to the horizon end when the duration is 0. The window is judged by the
   **order date**: orders already in transit when it starts keep their lead time, and with a review
   period > 1 a window that contains no review day affects no order. With `planner_aware = true` strategies see the adjusted mean lead time.
6. **Record** — ledger row (`sim.inventory_ledger`), purchase order (`sim.purchase_order`) and KPIs
   (data-model §6).

`z_t`, lateness and delay are pre-sampled **per item and day** from the run seed, so strategies compared on
the same seed face identical supply conditions (common random numbers). Initial state:
`ops.initial_inventory` (on hand = μ · (L̄ + order_cycle/2), on order 0). Capacity limits
(`ops.warehouse.capacity_units`) are reported as a warning when exceeded, not enforced (v0.1).
Demand-side scenario parameters are applied upstream by the demand generator, so the simulation lists them
as "not applied" in its warnings.

## 6. Demand for the horizon

- `demand_source = synthetic`: `time_series` generator calibrated on reference history before the
  horizon, scenario applied.
- `demand_source = reference`: actual reference demand over the horizon, scenario multipliers/shock applied
  deterministically (no resampling); useful as a sanity check.

Forecast models are trained only on data **before** the horizon start and see horizon demand only
as it is observed day by day (no look-ahead): the forecast runs on `derived.demand_timeline` (observed
history + synthetic horizon demand), each origin seeing only earlier days. Forecast-based strategies
need forecast errors from before the horizon, so the forecast run starts a **warm-up** period
(e.g. 56 days) before the horizon start, and its `forecast_horizon_days` must cover
reforecast interval + L̄ + R (e.g. 56).
