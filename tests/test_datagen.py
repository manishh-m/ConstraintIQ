"""Tests for synthetic data generation."""

import numpy as np
import pandas as pd
import pytest

from constraintiq.config import load_config
from constraintiq.datagen.demand import generate_demand
from constraintiq.datagen.network import build_network


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def demand(config):
    return generate_demand(config)


def test_demand_shape(config, demand):
    assert set(demand.columns) == {"date", "zone_id", "hub_id", "demand"}
    assert len(demand) == config.days * len(config.zones)


def test_demand_is_reproducible(config):
    d1 = generate_demand(config)
    d2 = generate_demand(config)
    pd.testing.assert_frame_equal(d1, d2)


def test_demand_non_negative(demand):
    assert (demand["demand"] >= 0).all()


def test_demand_covers_all_zones(config, demand):
    assert set(demand["zone_id"].unique()) == {z.id for z in config.zones}


def test_zone_trends_produce_growth(config, demand):
    """A zone with positive trend_per_day should have higher mean demand in the second half
    of the window than the first — confirms trend is actually being applied."""
    mid = config.days // 2
    dates = demand["date"].unique()
    first_half_end = dates[mid - 1]
    for zone in config.zones:
        if zone.trend_per_day <= 0:
            continue
        zd = demand[demand["zone_id"] == zone.id].copy()
        early = zd[zd["date"] <= first_half_end]["demand"].mean()
        late = zd[zd["date"] > first_half_end]["demand"].mean()
        assert late > early, f"{zone.id}: expected late > early given trend={zone.trend_per_day}"


def test_build_network_topology(config):
    network = build_network(config)
    assert set(network["hubs"].keys()) == {h.id for h in config.hubs}
    assert set(network["zones"].keys()) == {z.id for z in config.zones}
    # every zone appears in its hub's zone list
    for zone in config.zones:
        assert zone.id in network["hubs"][zone.hub]["zones"]
