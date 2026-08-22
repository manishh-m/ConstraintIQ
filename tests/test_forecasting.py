"""Tests for the forecasting layer."""

import numpy as np
import pandas as pd
import pytest

from constraintiq.config import load_config
from constraintiq.datagen.demand import generate_demand
from constraintiq.forecasting.evaluate import backtest, compare_models, mae, mape
from constraintiq.forecasting.models import (
    HoltWintersForecaster,
    NaiveSeasonalForecaster,
    forecast_all_zones,
)


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def demand(config):
    return generate_demand(config)


@pytest.fixture(scope="module")
def z1_series(demand):
    s = demand[demand["zone_id"] == "Z1"].set_index("date")["demand"].sort_index()
    s.index = pd.DatetimeIndex(s.index)
    return s


# --- model interface ---

def test_naive_predict_length(z1_series):
    m = NaiveSeasonalForecaster().fit(z1_series)
    pred = m.predict(14)
    assert len(pred) == 14


def test_holt_winters_predict_length(z1_series):
    m = HoltWintersForecaster().fit(z1_series)
    pred = m.predict(14)
    assert len(pred) == 14


def test_holt_winters_no_negatives(z1_series):
    m = HoltWintersForecaster().fit(z1_series)
    pred = m.predict(14)
    assert (pred >= 0).all()


def test_holt_winters_future_dates(z1_series):
    m = HoltWintersForecaster().fit(z1_series)
    pred = m.predict(14)
    assert pred.index[0] > z1_series.index[-1]


# --- metrics ---

def test_mape_perfect_forecast():
    a = pd.Series([100.0, 200.0, 150.0])
    assert mape(a, a) == pytest.approx(0.0)


def test_mae_perfect_forecast():
    a = pd.Series([100.0, 200.0])
    assert mae(a, a) == pytest.approx(0.0)


# --- backtest ---

def test_backtest_returns_expected_folds(z1_series):
    df = backtest(HoltWintersForecaster, z1_series, horizon=7, folds=4)
    assert len(df) == 4
    assert set(df.columns) >= {"fold", "cutoff_date", "mape_pct", "mae_parcels"}


def test_holt_winters_beats_naive(z1_series):
    """Core quality gate: Holt-Winters must outperform the naive baseline.

    If this fails, the model choice doesn't justify its complexity and we'd need to
    revisit (e.g. use ARIMA or check the demand generator).
    """
    summary = compare_models(z1_series, horizon=14, folds=5)
    hw_mape = summary.loc["holt_winters", "mean_mape_pct"]
    naive_mape = summary.loc["naive_seasonal", "mean_mape_pct"]
    assert hw_mape < naive_mape, (
        f"Holt-Winters MAPE ({hw_mape:.1f}%) should beat naive ({naive_mape:.1f}%)"
    )


# --- forecast_all_zones ---

def test_forecast_all_zones_shape(config, demand):
    forecasts = forecast_all_zones(demand, horizon=14)
    assert set(forecasts.columns) == {"date", "zone_id", "hub_id", "forecast_demand"}
    assert forecasts["zone_id"].nunique() == len(config.zones)
    assert len(forecasts) == len(config.zones) * 14


def test_forecast_all_zones_dates_are_future(demand):
    last_history_date = demand["date"].max()
    forecasts = forecast_all_zones(demand, horizon=14)
    assert (forecasts["date"] > last_history_date).all()
