"""Resolve the hub/zone topology from config into an in-memory network model.

Kept separate from demand generation so the topology (who serves whom, capacities) can be
reused by the ToC layer without pulling in any demand-simulation logic.
"""

from __future__ import annotations

from constraintiq.config import NetworkConfig


def build_network(config: NetworkConfig) -> dict:
    """Return a resolved topology consumed by both datagen and the ToC layer.

    Shape:
        {
            "hubs": {hub_id: {"name": ..., "capacity_per_day": ..., "zones": [zone_id, ...]}},
            "zones": {zone_id: {"name": ..., "hub": hub_id, "base_demand": ..., ...}},
        }
    """
    hubs: dict = {h.id: {"name": h.name, "capacity_per_day": h.capacity_per_day, "zones": []} for h in config.hubs}
    zones: dict = {}
    for z in config.zones:
        hubs[z.hub]["zones"].append(z.id)
        zones[z.id] = {
            "name": z.name,
            "hub": z.hub,
            "base_demand": z.base_demand,
            "trend_per_day": z.trend_per_day,
            "weekly_seasonality": z.weekly_seasonality,
        }
    return {"hubs": hubs, "zones": zones}
