"""Identify the current binding constraint in the network.

ToC framing: the binding constraint is the resource whose utilization is highest — the one
governing network throughput right now. With an elastic crowdsourced capacity model,
"utilization" is load / effective_capacity (not load / a fixed ceiling), and the binding
constraint is classified as hard (surge exhausted, genuine breach) or soft (surge deployed
but buffer remaining). This module answers "where is the constraint today and how severe is
it"; migration.py answers "where does it go next and when must we act".
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ResourceUtilization:
    resource_id: str
    resource_type: str      # "hub" | "zone"
    load: float
    base_capacity: float
    max_surge_capacity: float
    surge_lead_time_days: int

    @property
    def effective_capacity(self) -> float:
        """Base capacity plus surge actually needed (capped at max surge)."""
        surge_needed = max(0.0, self.load - self.base_capacity)
        surge_used = min(surge_needed, self.max_surge_capacity)
        return self.base_capacity + surge_used

    @property
    def utilization(self) -> float:
        """load / effective_capacity. >1.0 means a hard breach; =1.0 means soft; <1.0 normal."""
        ec = self.effective_capacity
        return self.load / ec if ec else float("inf")

    @property
    def is_soft(self) -> bool:
        return self.base_capacity < self.load <= self.effective_capacity

    @property
    def is_hard(self) -> bool:
        return self.load > self.effective_capacity


def _add_elastic_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorised helper: compute effective_capacity, utilization, is_soft, is_hard from load.

    Uses `surge_available` column as the surge ceiling when present (actual day-to-day
    availability from datagen); falls back to `max_surge_capacity` (the configured max)
    when the column is absent — e.g. for projected utilization where future availability
    is unknown.
    """
    surge_cap = df["surge_available"] if "surge_available" in df.columns else df["max_surge_capacity"]
    surge_needed = (df["load"] - df["base_capacity"]).clip(lower=0)
    surge_used = surge_needed.clip(upper=surge_cap)
    df = df.copy()
    df["effective_capacity"] = df["base_capacity"] + surge_used
    df["utilization"] = df["load"] / df["effective_capacity"]
    df["is_soft"] = (df["load"] > df["base_capacity"]) & (df["load"] <= df["effective_capacity"])
    df["is_hard"] = df["load"] > df["effective_capacity"]
    return df


def compute_utilization(
    demand: pd.DataFrame,
    network: dict,
    surge_availability: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Aggregate zone demand to hub load and return elastic utilization per hub per day.

    We model the constraint at hub level: a hub's throughput ceiling is what limits the
    whole sub-network it serves. Zone-level capacity limits are not modelled (no per-zone
    capacity in the config) so hubs are the only resource type here.

    Args:
        demand:             Tidy DataFrame [date, zone_id, hub_id, demand].
        network:            Topology dict from build_network() — carries base_capacity_per_day,
                            max_surge_capacity_per_day, and surge_lead_time_days per hub.
        surge_availability: Optional DataFrame [date, hub_id, surge_available] from
                            datagen.capacity.  When provided, `surge_available` (capped at
                            max_surge_capacity) replaces the fixed ceiling in the effective-
                            capacity formula — making the constraint model respond to
                            day-to-day gig-partner availability.  When None, falls back to
                            max_surge_capacity (identical to the original behaviour).

    Returns:
        DataFrame [date, resource_id, resource_type, load, base_capacity,
                   max_surge_capacity, surge_lead_time_days, surge_available,
                   effective_capacity, utilization, is_soft, is_hard],
                   sorted by date asc / utilization desc.
    """
    hub_load = (
        demand.groupby(["date", "hub_id"])["demand"]
        .sum()
        .reset_index()
        .rename(columns={"hub_id": "resource_id", "demand": "load"})
    )
    hub_load["resource_type"] = "hub"

    hubs = network["hubs"]
    hub_load["base_capacity"] = hub_load["resource_id"].map(
        {hid: meta["base_capacity_per_day"] for hid, meta in hubs.items()}
    )
    hub_load["max_surge_capacity"] = hub_load["resource_id"].map(
        {hid: meta["max_surge_capacity_per_day"] for hid, meta in hubs.items()}
    )
    hub_load["surge_lead_time_days"] = hub_load["resource_id"].map(
        {hid: meta["surge_lead_time_days"] for hid, meta in hubs.items()}
    )

    # Wire in actual day-by-day surge availability, capped at the configured maximum.
    if surge_availability is not None:
        avail = (
            surge_availability
            .rename(columns={"hub_id": "resource_id"})[["date", "resource_id", "surge_available"]]
        )
        hub_load = hub_load.merge(avail, on=["date", "resource_id"], how="left")
        hub_load["surge_available"] = (
            hub_load["surge_available"]
            .fillna(hub_load["max_surge_capacity"])
            .clip(upper=hub_load["max_surge_capacity"])
        )
    else:
        hub_load["surge_available"] = hub_load["max_surge_capacity"]

    hub_load = _add_elastic_columns(hub_load)

    cols = [
        "date", "resource_id", "resource_type", "load",
        "base_capacity", "max_surge_capacity", "surge_lead_time_days",
        "surge_available", "effective_capacity", "utilization", "is_soft", "is_hard",
    ]
    return hub_load[cols].sort_values(
        ["date", "utilization"], ascending=[True, False]
    ).reset_index(drop=True)


def identify_binding_constraint(utilization_day: pd.DataFrame) -> ResourceUtilization:
    """Return the binding constraint for a single day's utilization slice.

    Priority order — a deliberate design choice reflecting the gig-fleet operating model:

      1. Hard-constrained resources (load > effective_capacity, utilization > 1.0):
         ranked by utilization descending. These are active breaches — demand exceeds even
         maximum mobilised capacity and throughput is genuinely capped.

      2. Soft-constrained resources (base_capacity < load ≤ effective_capacity, util = 1.0):
         highest utilization. Surge is deployed but not yet exhausted — the buffer is
         shrinking and mobilisation must begin before lead time expires.

      3. All other resources (load ≤ base_capacity, utilization < 1.0):
         highest utilization — normal operation, no constraint pressure.

    Note: with the elastic-capacity formula, hard resources always have utilization > 1.0,
    soft resources have utilization = 1.0 exactly, and normal resources have utilization < 1.0.
    The priority ordering therefore maps to descending utilization, but the explicit priority
    logic is preserved here to document intent and to remain correct if the capacity formula
    ever changes.

    Args:
        utilization_day: Rows from compute_utilization() for one specific date.
    """
    if utilization_day.empty:
        raise ValueError("utilization_day DataFrame is empty.")

    hard = utilization_day[utilization_day["is_hard"]]
    if not hard.empty:
        top = hard.loc[hard["utilization"].idxmax()]
    else:
        soft = utilization_day[utilization_day["is_soft"]]
        if not soft.empty:
            top = soft.loc[soft["utilization"].idxmax()]
        else:
            top = utilization_day.loc[utilization_day["utilization"].idxmax()]

    return ResourceUtilization(
        resource_id=top["resource_id"],
        resource_type=top["resource_type"],
        load=float(top["load"]),
        base_capacity=float(top["base_capacity"]),
        max_surge_capacity=float(top["max_surge_capacity"]),
        surge_lead_time_days=int(top["surge_lead_time_days"]),
    )


def smooth_utilization(utilization: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """Apply a rolling mean to each resource's load to remove day-of-week noise.

    A constraint that flips every other day due to weekly seasonality is not an
    operationally meaningful migration. Smoothing over one weekly period (7 days)
    isolates trend-driven shifts from day-of-week effects.

    We smooth raw load (not utilization) to avoid circular dependency with the elastic
    effective_capacity formula, then recompute effective_capacity, utilization, is_soft,
    and is_hard from the smoothed load.
    """
    util = utilization.sort_values(["resource_id", "date"]).copy()
    util["load"] = (
        util.groupby("resource_id")["load"]
        .transform(lambda s: s.rolling(window, min_periods=1).mean())
    )
    util = _add_elastic_columns(util)
    return util.sort_values(
        ["date", "utilization"], ascending=[True, False]
    ).reset_index(drop=True)


def binding_constraint_history(utilization: pd.DataFrame, smooth: bool = True) -> pd.DataFrame:
    """Return the binding constraint (highest-priority resource) for every date.

    Args:
        utilization: Output of compute_utilization().
        smooth:      If True (default), apply 7-day rolling smoothing before identification
                     to suppress day-of-week noise. Pass False for raw daily granularity.

    Returns:
        DataFrame [date, resource_id, utilization, is_soft, is_hard] — one row per date.
    """
    u = smooth_utilization(utilization) if smooth else utilization
    idx = u.groupby("date")["utilization"].idxmax()
    result = u.loc[idx, ["date", "resource_id", "utilization", "is_soft", "is_hard"]].copy()
    return result.sort_values("date").reset_index(drop=True)
