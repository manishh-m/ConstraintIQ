"""Synthetic surge-availability generator.

Models the day-to-day variability in how much of a hub's surge (gig/crowdsourced)
fleet capacity is actually available to deploy — three effects layered on top of
each other:

1. Day-of-week:   gig partners are least available on weekends (demand peaks on
                  weekdays for them too, so supply competes with personal plans).
                  Represented as a multiplier on max_surge that dips Friday–Sunday.

2. Fatigue decay: consecutive days of heavy surge use reduce partner availability
                  the following day.  Modelled as a simple exponential decay that
                  resets when utilisation drops below a threshold.

3. Gaussian noise: residual day-to-day randomness, CV = surge_availability_noise_cv.

Output: a DataFrame with columns [date, hub_id, surge_available] where
surge_available ∈ [0, max_surge_capacity_per_day].
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from constraintiq.config import NetworkConfig

# Day-of-week multipliers (Monday=0 … Sunday=6).
# Gig partners are ~15% less available Fri–Sun.
_DOW_MULTIPLIER = np.array([1.00, 1.00, 0.98, 0.95, 0.90, 0.87, 0.85])

# Surge usage above this fraction of max_surge triggers fatigue the next day.
_FATIGUE_THRESHOLD = 0.70
# Each day of consecutive heavy use sheds this much availability (multiplicative).
_FATIGUE_DECAY_RATE = 0.05
# Maximum fatigue factor: availability never drops below 60% due to fatigue alone.
_MIN_FATIGUE_FACTOR = 0.60


def generate_surge_availability(
    config: NetworkConfig,
    surge_usage: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Generate a day × hub surge-availability DataFrame.

    Parameters
    ----------
    config:
        Loaded network configuration.
    surge_usage:
        Optional DataFrame with columns [date, hub_id, surge_used_fraction] that
        drives the fatigue model.  When None (or when a hub is absent), fatigue is
        zero and only day-of-week + noise are applied.

    Returns
    -------
    pd.DataFrame with columns [date, hub_id, surge_available].
        Values are clipped to [0, max_surge_capacity_per_day].
    """
    rng = np.random.default_rng(config.random_seed + 7)  # offset from demand seed

    dates = pd.date_range(config.start_date, periods=config.days, freq="D")
    dow = dates.dayofweek.to_numpy()  # 0=Mon, 6=Sun
    dow_factor = _DOW_MULTIPLIER[dow]  # shape (days,)

    # Pre-index surge_usage for fast lookup
    usage_lookup: dict[str, np.ndarray] = {}
    if surge_usage is not None:
        for hub_id, grp in surge_usage.groupby("hub_id"):
            grp_sorted = grp.sort_values("date").set_index("date")
            usage_lookup[str(hub_id)] = grp_sorted["surge_used_fraction"].to_numpy()

    records: list[dict] = []

    for hub in config.hubs:
        max_surge = hub.max_surge_capacity_per_day

        # Fatigue factor per day — iterative (each day depends on previous).
        fatigue_factor = np.ones(config.days)
        usage_arr = usage_lookup.get(hub.id)
        if usage_arr is not None and len(usage_arr) == config.days:
            consecutive = 0
            for d in range(config.days):
                frac = float(usage_arr[d])
                if frac >= _FATIGUE_THRESHOLD:
                    consecutive += 1
                else:
                    consecutive = 0
                decay = max(_MIN_FATIGUE_FACTOR, 1.0 - consecutive * _FATIGUE_DECAY_RATE)
                # Fatigue applies the *next* day; day 0 is never penalised.
                if d + 1 < config.days:
                    fatigue_factor[d + 1] = decay

        # Combine: base × dow × fatigue × gaussian noise, then clip.
        base = np.full(config.days, max_surge, dtype=float)
        noise = rng.normal(1.0, config.surge_availability_noise_cv, size=config.days)
        availability = base * dow_factor * fatigue_factor * noise
        availability = np.clip(availability, 0.0, max_surge)

        for d, date in enumerate(dates):
            records.append({
                "date": date,
                "hub_id": hub.id,
                "surge_available": round(float(availability[d]), 2),
            })

    return pd.DataFrame(records)
