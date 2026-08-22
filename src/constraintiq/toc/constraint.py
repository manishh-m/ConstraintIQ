"""Identify the current binding constraint in the network.

ToC framing: utilization = load / capacity. The binding constraint is the resource with the
highest utilization — the one governing network throughput right now. This module answers
"where is the constraint today"; migration.py answers "where does it go next".
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ResourceUtilization:
    resource_id: str
    resource_type: str  # "hub" | "zone"
    load: float
    capacity: float

    @property
    def utilization(self) -> float:
        return self.load / self.capacity if self.capacity else float("inf")


def compute_utilization(demand: pd.DataFrame, network: dict) -> pd.DataFrame:
    """Aggregate zone demand to hub load and return utilization per hub per day.

    We model the constraint at hub level: a hub's throughput ceiling is what limits the
    whole sub-network it serves. Zone-level capacity limits aren't modelled (no per-zone
    capacity in the config) so hubs are the only resource type here.

    Args:
        demand:  Tidy DataFrame [date, zone_id, hub_id, demand].
        network: Topology dict from build_network() — carries capacity_per_day per hub.

    Returns:
        DataFrame [date, resource_id, resource_type, load, capacity, utilization], sorted
        by date ascending then utilization descending.
    """
    hub_load = (
        demand.groupby(["date", "hub_id"])["demand"]
        .sum()
        .reset_index()
        .rename(columns={"hub_id": "resource_id", "demand": "load"})
    )
    hub_load["resource_type"] = "hub"
    hub_load["capacity"] = hub_load["resource_id"].map(
        {hid: meta["capacity_per_day"] for hid, meta in network["hubs"].items()}
    )
    hub_load["utilization"] = hub_load["load"] / hub_load["capacity"]

    return hub_load[["date", "resource_id", "resource_type", "load", "capacity", "utilization"]].sort_values(
        ["date", "utilization"], ascending=[True, False]
    ).reset_index(drop=True)


def identify_binding_constraint(utilization_day: pd.DataFrame) -> ResourceUtilization:
    """Return the binding constraint for a single day's utilization slice.

    Args:
        utilization_day: Rows from compute_utilization() for one specific date.
    """
    if utilization_day.empty:
        raise ValueError("utilization_day DataFrame is empty.")
    top = utilization_day.loc[utilization_day["utilization"].idxmax()]
    return ResourceUtilization(
        resource_id=top["resource_id"],
        resource_type=top["resource_type"],
        load=float(top["load"]),
        capacity=float(top["capacity"]),
    )


def smooth_utilization(utilization: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """Apply a rolling mean to each resource's utilization to remove day-of-week noise.

    A constraint that flips every other day due to seasonality isn't an operationally
    meaningful migration. Smoothing over one weekly period (7 days) isolates trend-driven
    shifts from day-of-week effects.
    """
    util = utilization.sort_values(["resource_id", "date"]).copy()
    util["utilization"] = (
        util.groupby("resource_id")["utilization"]
        .transform(lambda s: s.rolling(window, min_periods=1).mean())
    )
    # Recompute load consistently with smoothed utilization
    util["load"] = util["utilization"] * util["capacity"]
    return util.sort_values(["date", "utilization"], ascending=[True, False]).reset_index(drop=True)


def binding_constraint_history(utilization: pd.DataFrame, smooth: bool = True) -> pd.DataFrame:
    """Return the binding constraint (highest-utilization resource) for every date.

    Args:
        utilization: Output of compute_utilization().
        smooth:      If True (default), apply 7-day rolling smoothing before identification
                     to suppress day-of-week noise. Pass False for raw daily granularity.

    Returns:
        DataFrame [date, resource_id, utilization] — one row per date.
    """
    u = smooth_utilization(utilization) if smooth else utilization
    idx = u.groupby("date")["utilization"].idxmax()
    result = u.loc[idx, ["date", "resource_id", "utilization"]].copy()
    return result.sort_values("date").reset_index(drop=True)
