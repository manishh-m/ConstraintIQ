"""Tests for the surge-availability generator (datagen/capacity.py)."""

import numpy as np
import pandas as pd
import pytest

from constraintiq.config import load_config
from constraintiq.datagen.capacity import generate_surge_availability


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def availability(config):
    return generate_surge_availability(config)


# ── shape & schema ─────────────────────────────────────────────────────────────

def test_shape(config, availability):
    """One row per hub per day."""
    assert len(availability) == config.days * len(config.hubs)


def test_columns(availability):
    assert set(availability.columns) >= {"date", "hub_id", "surge_available"}


def test_all_hubs_present(config, availability):
    assert set(availability["hub_id"].unique()) == {h.id for h in config.hubs}


def test_all_dates_present(config, availability):
    expected = set(pd.date_range(config.start_date, periods=config.days, freq="D"))
    assert set(availability["date"].unique()) == expected


# ── value constraints ──────────────────────────────────────────────────────────

def test_non_negative(availability):
    assert (availability["surge_available"] >= 0).all()


def test_never_exceeds_max_surge(config, availability):
    """surge_available must never exceed max_surge_capacity_per_day for each hub."""
    for hub in config.hubs:
        hub_rows = availability[availability["hub_id"] == hub.id]
        assert (hub_rows["surge_available"] <= hub.max_surge_capacity_per_day).all(), (
            f"{hub.id}: surge_available exceeds max_surge_capacity_per_day "
            f"({hub.max_surge_capacity_per_day})"
        )


# ── reproducibility ────────────────────────────────────────────────────────────

def test_reproducible(config):
    """Two calls with the same config must produce identical results."""
    a1 = generate_surge_availability(config)
    a2 = generate_surge_availability(config)
    pd.testing.assert_frame_equal(a1.reset_index(drop=True), a2.reset_index(drop=True))


# ── day-of-week effect ─────────────────────────────────────────────────────────

def test_weekends_lower_than_weekdays_on_average(config, availability):
    """Weekend availability should be lower than weekday availability on average
    (the DOW multiplier drops Fri–Sun by 10–15%)."""
    df = availability.copy()
    df["dow"] = pd.to_datetime(df["date"]).dt.dayofweek
    df["is_weekend"] = df["dow"] >= 4  # Fri=4, Sat=5, Sun=6

    weekday_mean = df[~df["is_weekend"]]["surge_available"].mean()
    weekend_mean = df[df["is_weekend"]]["surge_available"].mean()
    assert weekend_mean < weekday_mean, (
        f"Expected weekend mean ({weekend_mean:.1f}) < weekday mean ({weekday_mean:.1f})"
    )


# ── fatigue model ──────────────────────────────────────────────────────────────

def test_fatigue_reduces_next_day_availability(config):
    """When surge is heavily used for multiple consecutive days, the next-day
    availability should be lower than when surge is not used at all."""
    days = config.days

    # Build a usage series: all days at 100% surge utilisation.
    hub_id = config.hubs[0].id
    dates = pd.date_range(config.start_date, periods=days, freq="D")
    full_usage = pd.DataFrame({
        "date": dates,
        "hub_id": hub_id,
        "surge_used_fraction": np.ones(days),
    })

    no_usage = full_usage.copy()
    no_usage["surge_used_fraction"] = 0.0

    avail_heavy = generate_surge_availability(config, surge_usage=full_usage)
    avail_none  = generate_surge_availability(config, surge_usage=no_usage)

    heavy_mean = avail_heavy[avail_heavy["hub_id"] == hub_id]["surge_available"].mean()
    none_mean  = avail_none[avail_none["hub_id"] == hub_id]["surge_available"].mean()

    assert heavy_mean < none_mean, (
        f"Heavy-use mean ({heavy_mean:.1f}) should be < no-use mean ({none_mean:.1f})"
    )
