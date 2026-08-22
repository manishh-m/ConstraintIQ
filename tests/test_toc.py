"""Tests for the Theory of Constraints layer."""

import pandas as pd
import pytest

from constraintiq.config import load_config
from constraintiq.datagen.demand import generate_demand
from constraintiq.datagen.network import build_network
from constraintiq.toc.constraint import (
    ResourceUtilization,
    binding_constraint_history,
    compute_utilization,
    identify_binding_constraint,
)
from constraintiq.toc.migration import (
    MigrationEvent,
    detect_migration,
    project_future_utilization,
)
from constraintiq.forecasting.models import forecast_all_zones


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def network(config):
    return build_network(config)


@pytest.fixture(scope="module")
def demand(config):
    return generate_demand(config)


@pytest.fixture(scope="module")
def utilization(demand, network):
    return compute_utilization(demand, network)


@pytest.fixture(scope="module")
def forecasts(config, demand):
    return forecast_all_zones(demand, horizon=config.forecast_horizon)


@pytest.fixture(scope="module")
def projected(forecasts, network):
    return project_future_utilization(forecasts, network)


# --- compute_utilization ---

def test_utilization_has_expected_columns(utilization):
    assert set(utilization.columns) >= {"date", "resource_id", "resource_type", "load", "capacity", "utilization"}


def test_utilization_covers_all_hubs(config, utilization):
    hub_ids = {h.id for h in config.hubs}
    assert set(utilization["resource_id"].unique()) == hub_ids


def test_utilization_one_row_per_hub_per_day(config, utilization):
    counts = utilization.groupby("date")["resource_id"].count()
    assert (counts == len(config.hubs)).all()


def test_utilization_load_matches_zone_sum(config, demand, utilization):
    """Hub load must equal the sum of demand across all its zones for every day."""
    for hub in config.hubs:
        hub_zones = [z.id for z in config.zones if z.hub == hub.id]
        zone_total = demand[demand["zone_id"].isin(hub_zones)].groupby("date")["demand"].sum()
        hub_load = utilization[utilization["resource_id"] == hub.id].set_index("date")["load"]
        pd.testing.assert_series_equal(zone_total.sort_index(), hub_load.sort_index(), check_names=False, rtol=1e-3)


# --- identify_binding_constraint ---

def test_binding_constraint_is_highest_utilization(utilization):
    """The binding constraint must always be the resource with maximum utilization."""
    for date, group in utilization.groupby("date"):
        bc = identify_binding_constraint(group)
        assert bc.utilization == pytest.approx(group["utilization"].max(), rel=1e-4)


def test_binding_constraint_history_one_row_per_day(config, utilization):
    history = binding_constraint_history(utilization)
    assert len(history) == config.days
    assert history["date"].nunique() == config.days


# --- projection ---

def test_projected_utilization_covers_forecast_horizon(config, projected):
    assert projected["date"].nunique() == config.forecast_horizon


def test_projected_utilization_dates_are_after_history(demand, projected):
    last_history = demand["date"].max()
    assert (projected["date"] > last_history).all()


# --- detect_migration ---

def test_detect_migration_returns_list(projected):
    events = detect_migration(projected)
    assert isinstance(events, list)


def test_migration_events_are_chronological(projected):
    events = detect_migration(projected)
    days = [e.day for e in events]
    assert days == sorted(days)


def test_migration_event_fields(projected):
    events = detect_migration(projected)
    for e in events:
        assert isinstance(e, MigrationEvent)
        assert e.from_resource != e.to_resource
        assert e.projected_utilization > 0


def test_known_migration_occurs(config, demand, network):
    """The synthetic data is designed so that HUB_NORTH becomes constrained as Z3
    (trend +20/day) and Z1 (trend +12/day) push its total load past 12 000 parcels/day.
    Over a long enough horizon the constraint must shift to or stay at HUB_NORTH.

    This test uses a 60-day horizon so the known constraint-breach is visible.
    """
    forecasts_long = forecast_all_zones(demand, horizon=60)
    projected_long = project_future_utilization(forecasts_long, network)

    # By the end of the 60-day horizon HUB_NORTH should be the binding constraint
    last_date = projected_long["date"].max()
    last_day = projected_long[projected_long["date"] == last_date]
    bc = identify_binding_constraint(last_day)
    assert bc.resource_id == "HUB_NORTH", (
        f"Expected HUB_NORTH to be constrained by end of 60-day horizon, got {bc.resource_id} "
        f"({bc.utilization:.1%} utilisation)"
    )
