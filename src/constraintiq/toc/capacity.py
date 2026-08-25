"""Elastic capacity model for a gig/crowdsourced delivery fleet.

ToC framing — "elevate the constraint":
  Goldratt's fifth step is to elevate the constraint by expanding throughput capacity.
  For a captive fleet this is slow and expensive (hire, train, asset purchase). For a
  crowdsourced fleet it is faster but not instant: a hub has a base captive pool it
  controls directly, plus a surge pool of freelance riders it can mobilise with
  adequate lead time.

  This means capacity is NOT a hard wall:
    - Below base_capacity   → constraint is dormant; no surge needed.
    - base < load ≤ base+surge → SOFT constraint: the gap is covered by surge, but the
      buffer is shrinking. The hub is technically operating, but only because surge is
      deployed. This is the actionable early-warning signal.
    - load > base+max_surge → HARD constraint: even full surge mobilisation cannot cover
      demand. Throughput is genuinely capped. This is the breach state — immediate
      intervention (permanent capacity addition, demand re-routing, SLA revision) is
      required.

  Surge requires lead time (surge_lead_time_days) to mobilise. The `act_by_date` on a
  migration event tells operations the latest date to trigger activation to avoid a hard
  breach. That window is the single most actionable output ConstraintIQ produces.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapacityState:
    """Snapshot of a single hub's capacity situation on a given day.

    Args:
        resource_id:           Hub identifier.
        base_capacity:         Captive-fleet throughput ceiling (parcels/day).
        max_surge_capacity:    Maximum additional throughput mobilisable via surge.
        surge_lead_time_days:  Days of advance notice required to activate surge.
        load:                  Actual demand placed on this hub (parcels/day).
    """

    resource_id: str
    base_capacity: float
    max_surge_capacity: float
    surge_lead_time_days: int
    load: float

    @property
    def effective_capacity(self) -> float:
        """Base capacity plus however much surge is needed (capped at max surge)."""
        surge_needed = max(0.0, self.load - self.base_capacity)
        surge_used = min(surge_needed, self.max_surge_capacity)
        return self.base_capacity + surge_used

    @property
    def surge_utilization(self) -> float:
        """Fraction of max surge capacity currently in use (0.0 if no surge pool)."""
        if self.max_surge_capacity == 0:
            return 0.0
        surge_needed = max(0.0, self.load - self.base_capacity)
        surge_used = min(surge_needed, self.max_surge_capacity)
        return surge_used / self.max_surge_capacity

    @property
    def is_soft_constraint(self) -> bool:
        """True when surge is covering the gap but capacity is not yet exhausted."""
        return self.base_capacity < self.load <= self.effective_capacity

    @property
    def is_hard_constraint(self) -> bool:
        """True when load exceeds even max-surge effective capacity — a genuine breach."""
        return self.load > self.effective_capacity


def compute_capacity_state(
    resource_id: str,
    load: float,
    hub_config: dict,
) -> CapacityState:
    """Build a CapacityState from the hub's network-topology entry.

    Args:
        resource_id: Hub identifier (e.g. "HUB_NORTH").
        load:        Current or projected load (parcels/day).
        hub_config:  The hub's dict from build_network() — must contain
                     base_capacity_per_day, max_surge_capacity_per_day,
                     surge_lead_time_days.
    """
    return CapacityState(
        resource_id=resource_id,
        base_capacity=float(hub_config["base_capacity_per_day"]),
        max_surge_capacity=float(hub_config["max_surge_capacity_per_day"]),
        surge_lead_time_days=int(hub_config["surge_lead_time_days"]),
        load=float(load),
    )
