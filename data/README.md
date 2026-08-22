# Data

All data in ConstraintIQ is **synthetic**. There is no real last-mile operational dataset
behind this project — none was available — so demand, capacities, and network topology are
generated from the parameters in [`../config/network.yaml`](../config/network.yaml).

This is a deliberate design choice, stated up front rather than buried: the value of the
prototype is in the *reasoning* (ToC constraint modeling + forecasting), and that can be
evaluated honestly on transparent synthetic data.

## What gets generated

`synthetic/` (gitignored, regenerable via `uv run python -m constraintiq.datagen`):

- **`demand.parquet`** — daily parcel demand per zone over the simulation window.
- **`network.json`** — resolved hub/zone topology and capacities.

## How the synthetic demand is modelled

For each zone, daily demand is:

```
demand(t) = base_demand
          + trend_per_day * t                  # linear drift (drives constraint migration)
          + weekly_seasonality component        # day-of-week effect
          + gaussian noise (cv = noise.demand_cv)
```

Hub load on a given day is the sum of demand across the zones it serves. A hub (or zone) is
**constrained** when projected load approaches or exceeds its `capacity_per_day` ceiling. The
differing `trend_per_day` values across zones are what cause the binding constraint to shift
over time — that migration is exactly what ConstraintIQ is built to predict.

Assumptions and their limitations are documented in
[`../docs/methodology.md`](../docs/methodology.md).
