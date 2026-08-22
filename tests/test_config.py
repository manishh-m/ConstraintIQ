"""Tests for config loading."""

import pytest

from constraintiq.config import load_config


def test_load_config_parses_hubs_and_zones():
    config = load_config()
    assert len(config.hubs) == 2
    assert len(config.zones) >= 6
    hub_ids = {h.id for h in config.hubs}
    assert all(z.hub in hub_ids for z in config.zones)


def test_load_config_simulation_params():
    config = load_config()
    assert config.days > 0
    assert config.forecast_horizon > 0
    assert 0.0 < config.demand_cv < 1.0


def test_load_config_rejects_bad_zone_hub(tmp_path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("""
simulation: {start_date: "2026-01-01", days: 10, forecast_horizon: 7, random_seed: 0}
hubs:
  - {id: HUB_A, name: "A", capacity_per_day: 1000}
zones:
  - {id: Z1, name: "Zone 1", hub: HUB_MISSING, base_demand: 500, trend_per_day: 1.0, weekly_seasonality: 0.1}
noise: {demand_cv: 0.05}
""")
    with pytest.raises(ValueError, match="unknown hub ids"):
        load_config(bad_yaml)
