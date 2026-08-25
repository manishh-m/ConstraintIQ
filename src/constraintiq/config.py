"""Load and validate the network scenario from config/network.yaml.

Centralizing config parsing here keeps the datagen, forecasting, and ToC layers decoupled
from the on-disk YAML format.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# Repo-root-relative default. Callers may pass an explicit path.
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "network.yaml"


@dataclass(frozen=True)
class Hub:
    id: str
    name: str
    base_capacity_per_day: float
    max_surge_capacity_per_day: float
    surge_lead_time_days: int


@dataclass(frozen=True)
class Zone:
    id: str
    name: str
    hub: str
    base_demand: float
    trend_per_day: float
    weekly_seasonality: float


@dataclass(frozen=True)
class NetworkConfig:
    start_date: str
    days: int
    forecast_horizon: int
    random_seed: int
    hubs: list[Hub]
    zones: list[Zone]
    demand_cv: float
    surge_availability_noise_cv: float


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> NetworkConfig:
    """Parse network.yaml into a validated NetworkConfig."""
    raw = yaml.safe_load(Path(path).read_text())

    hubs = [Hub(**h) for h in raw["hubs"]]
    hub_ids = {h.id for h in hubs}

    zones = [Zone(**z) for z in raw["zones"]]
    bad = [z.id for z in zones if z.hub not in hub_ids]
    if bad:
        raise ValueError(f"Zones reference unknown hub ids: {bad}")

    sim = raw["simulation"]
    return NetworkConfig(
        start_date=sim["start_date"],
        days=sim["days"],
        forecast_horizon=sim["forecast_horizon"],
        random_seed=sim["random_seed"],
        hubs=hubs,
        zones=zones,
        demand_cv=raw["noise"]["demand_cv"],
        surge_availability_noise_cv=raw["noise"]["surge_availability_noise_cv"],
    )
