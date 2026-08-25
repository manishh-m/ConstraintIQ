"""Tests for the Theory of Constraints layer."""

import pandas as pd
import pytest

from constraintiq.config import load_config
from constraintiq.datagen.demand import generate_demand
from constraintiq.datagen.network import build_network
from constraintiq.toc.capacity import CapacityState, compute_capacity_state, surge_incentive_cost
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


# ── compute_utilization ────────────────────────────────────────────────────────

def test_utilization_has_expected_columns(utilization):
    assert set(utilization.columns) >= {
        "date", "resource_id", "resource_type", "load",
        "base_capacity", "max_surge_capacity", "surge_lead_time_days",
        "surge_available", "effective_capacity", "utilization", "is_soft", "is_hard",
    }


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


def test_effective_capacity_never_below_base(utilization):
    assert (utilization["effective_capacity"] >= utilization["base_capacity"]).all()


def test_hard_and_soft_are_mutually_exclusive(utilization):
    assert not (utilization["is_hard"] & utilization["is_soft"]).any()


def test_hard_implies_utilization_above_one(utilization):
    hard = utilization[utilization["is_hard"]]
    assert (hard["utilization"] > 1.0).all()


def test_soft_implies_utilization_at_one(utilization):
    soft = utilization[utilization["is_soft"]]
    # Soft: load == effective_capacity, so utilization == 1.0 exactly
    assert (soft["utilization"].round(10) == 1.0).all()


# ── identify_binding_constraint ───────────────────────────────────────────────

def test_binding_constraint_is_highest_utilization(utilization):
    """Binding constraint must always have the highest utilization in the slice.
    With elastic capacity, hard > 1.0 > soft == 1.0 > normal < 1.0, so the
    priority rule and argmax(utilization) are equivalent."""
    for date, group in utilization.groupby("date"):
        bc = identify_binding_constraint(group)
        assert bc.utilization == pytest.approx(group["utilization"].max(), rel=1e-4)


def test_binding_constraint_history_one_row_per_day(config, utilization):
    history = binding_constraint_history(utilization)
    assert len(history) == config.days
    assert history["date"].nunique() == config.days


def test_identify_binding_constraint_prefers_hard_over_soft():
    """A hard-constrained hub must win over a soft-constrained hub with higher raw load."""
    # HUB_A: soft  — load=10500, base=10000, max_surge=1000 → effective=10500, util=1.0
    # HUB_B: hard  — load=5500,  base=5000,  max_surge=400  → effective=5400,  util≈1.019
    # Despite HUB_A carrying more load, HUB_B is a hard breach and must be flagged first.
    data = pd.DataFrame({
        "date":               [pd.Timestamp("2026-01-01")] * 2,
        "resource_id":        ["HUB_A", "HUB_B"],
        "resource_type":      ["hub", "hub"],
        "load":               [10500.0, 5500.0],
        "base_capacity":      [10000.0, 5000.0],
        "max_surge_capacity": [1000.0,  400.0],
        "surge_lead_time_days": [3, 3],
        "effective_capacity": [10500.0, 5400.0],
        "utilization":        [10500.0 / 10500.0, 5500.0 / 5400.0],
        "is_soft":            [True,  False],
        "is_hard":            [False, True],
    })
    bc = identify_binding_constraint(data)
    assert bc.resource_id == "HUB_B"
    assert bc.is_hard


def test_identify_binding_constraint_prefers_soft_over_normal():
    """A soft-constrained hub must win over a normal hub even with lower raw utilization."""
    # HUB_A: normal — load=8000, base=10000 → util=0.80
    # HUB_B: soft   — load=5500, base=5000, max_surge=1000 → effective=5500, util=1.0
    data = pd.DataFrame({
        "date":               [pd.Timestamp("2026-01-01")] * 2,
        "resource_id":        ["HUB_A", "HUB_B"],
        "resource_type":      ["hub", "hub"],
        "load":               [8000.0, 5500.0],
        "base_capacity":      [10000.0, 5000.0],
        "max_surge_capacity": [2000.0, 1000.0],
        "surge_lead_time_days": [3, 3],
        "effective_capacity": [10000.0, 5500.0],
        "utilization":        [8000.0 / 10000.0, 5500.0 / 5500.0],
        "is_soft":            [False, True],
        "is_hard":            [False, False],
    })
    bc = identify_binding_constraint(data)
    assert bc.resource_id == "HUB_B"
    assert bc.is_soft


# ── projection ────────────────────────────────────────────────────────────────

def test_projected_utilization_covers_forecast_horizon(config, projected):
    assert projected["date"].nunique() == config.forecast_horizon


def test_projected_utilization_dates_are_after_history(demand, projected):
    last_history = demand["date"].max()
    assert (projected["date"] > last_history).all()


# ── detect_migration ──────────────────────────────────────────────────────────

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
        assert isinstance(e.act_by_date, pd.Timestamp)


def test_act_by_date_equals_day_minus_lead_time(config, projected):
    """act_by_date must equal the migration day minus the incoming hub's surge_lead_time_days."""
    events = detect_migration(projected)
    for e in events:
        lead = next(h.surge_lead_time_days for h in config.hubs if h.id == e.to_resource)
        expected = e.day - pd.Timedelta(days=lead)
        assert e.act_by_date == expected


def test_known_migration_occurs(config, demand, network):
    """The synthetic data is designed so that HUB_NORTH becomes constrained as Z3
    (trend +20/day) and Z1 (trend +12/day) push its total load well past its base
    capacity. Over a long enough horizon the constraint must settle at HUB_NORTH.

    This test uses a 60-day horizon so the known constraint-breach is visible.
    """
    forecasts_long = forecast_all_zones(demand, horizon=60)
    projected_long = project_future_utilization(forecasts_long, network)

    last_date = projected_long["date"].max()
    last_day = projected_long[projected_long["date"] == last_date]
    bc = identify_binding_constraint(last_day)
    assert bc.resource_id == "HUB_NORTH", (
        f"Expected HUB_NORTH to be constrained by end of 60-day horizon, got {bc.resource_id} "
        f"({bc.utilization:.1%} utilisation)"
    )


# ── compute_capacity_state ────────────────────────────────────────────────────

def _hub_cfg(base, max_surge, lead):
    return {
        "base_capacity_per_day": base,
        "max_surge_capacity_per_day": max_surge,
        "surge_lead_time_days": lead,
    }


def test_capacity_state_normal():
    """Load within base capacity — no surge, normal operation."""
    state = compute_capacity_state("HUB_X", 8000.0, _hub_cfg(10000, 2000, 3))
    assert state.effective_capacity == pytest.approx(10000.0)
    assert state.surge_utilization == pytest.approx(0.0)
    assert not state.is_soft_constraint
    assert not state.is_hard_constraint


def test_capacity_state_soft():
    """Load above base but within base+surge — soft constraint, surge partially deployed."""
    state = compute_capacity_state("HUB_X", 11000.0, _hub_cfg(10000, 2000, 3))
    assert state.effective_capacity == pytest.approx(11000.0)   # base + 1000 surge
    assert state.surge_utilization == pytest.approx(0.5)        # 1000 of 2000 used
    assert state.is_soft_constraint
    assert not state.is_hard_constraint


def test_capacity_state_hard():
    """Load exceeds base+max_surge — hard constraint, genuine throughput breach."""
    state = compute_capacity_state("HUB_X", 12500.0, _hub_cfg(10000, 2000, 3))
    assert state.effective_capacity == pytest.approx(12000.0)   # base + max_surge (capped)
    assert state.surge_utilization == pytest.approx(1.0)
    assert not state.is_soft_constraint
    assert state.is_hard_constraint


def test_capacity_state_boundary_base():
    """Load exactly at base capacity — still normal, no surge needed."""
    state = compute_capacity_state("HUB_X", 10000.0, _hub_cfg(10000, 2000, 3))
    assert state.effective_capacity == pytest.approx(10000.0)
    assert state.surge_utilization == pytest.approx(0.0)
    assert not state.is_soft_constraint
    assert not state.is_hard_constraint


def test_capacity_state_boundary_max_surge():
    """Load exactly at base+max_surge — still soft (not hard), surge fully deployed."""
    state = compute_capacity_state("HUB_X", 12000.0, _hub_cfg(10000, 2000, 3))
    assert state.effective_capacity == pytest.approx(12000.0)
    assert state.surge_utilization == pytest.approx(1.0)
    assert state.is_soft_constraint
    assert not state.is_hard_constraint


def test_capacity_state_zero_surge_pool():
    """Hub with no surge pool at all — any overload is immediately hard."""
    state_over = compute_capacity_state("HUB_X", 10001.0, _hub_cfg(10000, 0, 0))
    assert state_over.is_hard_constraint
    assert state_over.surge_utilization == pytest.approx(0.0)

    state_ok = compute_capacity_state("HUB_X", 9999.0, _hub_cfg(10000, 0, 0))
    assert not state_ok.is_hard_constraint
    assert not state_ok.is_soft_constraint


# ── surge_incentive_cost ──────────────────────────────────────────────────────

def test_surge_cost_no_surge_is_one():
    """Zero surge units → multiplier = 1.0 (no premium)."""
    assert surge_incentive_cost(0.0, 2000.0, 3, 3) == pytest.approx(1.0)


def test_surge_cost_no_surge_pool_is_one():
    """Hub with no surge pool → multiplier = 1.0."""
    assert surge_incentive_cost(500.0, 0.0, 0, 3) == pytest.approx(1.0)


def test_surge_cost_volume_premium_convex():
    """Volume premium alone (lead time met): 1 + 0.5 * fraction²."""
    # 50% of max_surge → fraction=0.5 → premium = 1 + 0.5*0.25 = 1.125
    cost_half = surge_incentive_cost(1000.0, 2000.0, 5, 3)   # lead time met
    assert cost_half == pytest.approx(1.125)

    # 100% of max_surge → fraction=1.0 → premium = 1 + 0.5*1 = 1.5
    cost_full = surge_incentive_cost(2000.0, 2000.0, 5, 3)
    assert cost_full == pytest.approx(1.5)

    # Full surge costs more than half surge
    assert cost_full > cost_half


def test_surge_cost_short_notice_penalty():
    """Each day short of required lead time adds 50% to the total multiplier."""
    # 2 days short → short_notice_hit = 1 + 0.5*2 = 2.0; volume at 50% → 1.125
    cost = surge_incentive_cost(1000.0, 2000.0, 1, 3)  # given=1, required=3 → 2 days short
    assert cost == pytest.approx(1.125 * 2.0)


def test_surge_cost_lead_time_met_no_penalty():
    """No penalty when given lead time equals or exceeds required."""
    cost_exact  = surge_incentive_cost(1000.0, 2000.0, 3, 3)
    cost_excess = surge_incentive_cost(1000.0, 2000.0, 5, 3)
    assert cost_exact  == pytest.approx(1.125)
    assert cost_excess == pytest.approx(1.125)


def test_surge_cost_multiplier_property_normal_state():
    """No surge deployed → surge_cost_multiplier = 1.0."""
    state = compute_capacity_state("HUB_X", 8000.0, _hub_cfg(10000, 2000, 3))
    assert state.surge_cost_multiplier == pytest.approx(1.0)


def test_surge_cost_multiplier_property_soft():
    """Soft constraint with zero notice (worst-case): fraction=0.5, shortfall=3."""
    # load=11000, base=10000, max_surge=2000 → surge_used=1000, fraction=0.5
    # volume_premium = 1.125, short_notice_hit = 1 + 0.5*3 = 2.5
    state = compute_capacity_state("HUB_X", 11000.0, _hub_cfg(10000, 2000, 3))
    assert state.surge_cost_multiplier == pytest.approx(1.125 * 2.5)
