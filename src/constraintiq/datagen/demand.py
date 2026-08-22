"""Generate synthetic daily demand per zone.

Model (see data/README.md for rationale):
    demand(t) = base_demand
              + trend_per_day * t
              + base_demand * weekly_seasonality * day_of_week_effect[dow]
              + gaussian noise  (std = demand_cv * base_demand)

Differing per-zone trends are what make the binding constraint migrate over time.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from constraintiq.config import NetworkConfig

# Relative multipliers for Mon–Sun. Logistics demand peaks mid-week and dips Sunday.
_DOW_EFFECT = np.array([0.05, 0.10, 0.10, 0.05, 0.00, -0.10, -0.20])


def generate_demand(config: NetworkConfig) -> pd.DataFrame:
    """Return a tidy DataFrame with columns [date, zone_id, hub_id, demand].

    Demand is clipped at 0 — negative parcel volumes don't make sense.
    """
    rng = np.random.default_rng(config.random_seed)
    dates = pd.date_range(config.start_date, periods=config.days, freq="D")
    t = np.arange(config.days, dtype=float)
    dow = dates.dayofweek.to_numpy()  # 0=Mon … 6=Sun

    rows: list[dict] = []
    for zone in config.zones:
        trend = zone.trend_per_day * t
        seasonality = zone.base_demand * zone.weekly_seasonality * _DOW_EFFECT[dow]
        noise_std = zone.base_demand * config.demand_cv
        noise = rng.normal(0.0, noise_std, size=config.days)

        demand = np.clip(zone.base_demand + trend + seasonality + noise, 0.0, None)

        for i, date in enumerate(dates):
            rows.append({
                "date": date,
                "zone_id": zone.id,
                "hub_id": zone.hub,
                "demand": round(demand[i], 1),
            })

    return pd.DataFrame(rows)
