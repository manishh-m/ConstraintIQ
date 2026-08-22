"""Forecasting models behind a common interface.

A single `Forecaster` protocol lets the pipeline swap models without changing downstream ToC
code. Rule: every model must beat NaiveSeasonalForecaster in backtest before it's used in
the pipeline — complexity has to earn its keep.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


class Forecaster(Protocol):
    """Common interface for all forecasting models."""

    def fit(self, history: pd.Series) -> "Forecaster": ...

    def predict(self, horizon: int) -> pd.Series:
        """Return `horizon` future daily values as a DatetimeIndex Series."""
        ...


class NaiveSeasonalForecaster:
    """Baseline: tile the last 7 days of observed demand forward.

    This is the bar every model must beat. If Holt-Winters can't outperform "repeat last
    week", it adds no value over a simple look-up table.
    """

    _last_week: pd.Series

    def fit(self, history: pd.Series) -> "NaiveSeasonalForecaster":
        if len(history) < 7:
            raise ValueError("Need at least 7 days of history for naive seasonal baseline.")
        self._last_week = history.iloc[-7:].values
        self._last_date = history.index[-1]
        return self

    def predict(self, horizon: int) -> pd.Series:
        future_dates = pd.date_range(self._last_date + pd.Timedelta(days=1), periods=horizon, freq="D")
        repeated = np.tile(self._last_week, (horizon // 7) + 1)[:horizon]
        return pd.Series(repeated, index=future_dates)


class HoltWintersForecaster:
    """Triple exponential smoothing (additive trend + additive weekly seasonality).

    Chosen because:
    - Handles the linear trend in synthetic demand (trend_per_day drift).
    - Handles the day-of-week seasonality (period=7).
    - Fully explainable: each component maps directly to something visible in the data.
    - Beats naive seasonal on any series with meaningful trend — which is the whole point
      of the synthetic data design.
    """

    _fitted: ExponentialSmoothing

    def fit(self, history: pd.Series) -> "HoltWintersForecaster":
        if len(history) < 14:
            raise ValueError("Need at least 14 days (2 seasonal periods) for Holt-Winters.")
        model = ExponentialSmoothing(
            history,
            trend="add",
            seasonal="add",
            seasonal_periods=7,
            initialization_method="estimated",
        )
        self._fitted = model.fit(optimized=True)
        self._last_date = history.index[-1]
        return self

    def predict(self, horizon: int) -> pd.Series:
        forecast_values = self._fitted.forecast(horizon)
        future_dates = pd.date_range(self._last_date + pd.Timedelta(days=1), periods=horizon, freq="D")
        clipped = np.clip(forecast_values.values, 0.0, None)
        return pd.Series(clipped, index=future_dates)


def forecast_all_zones(
    demand: pd.DataFrame,
    horizon: int,
    model_cls: type = HoltWintersForecaster,
) -> pd.DataFrame:
    """Fit one forecaster per zone and return a tidy forecast DataFrame.

    Returns: [date, zone_id, hub_id, forecast_demand]
    """
    records: list[dict] = []
    zone_hub = demand[["zone_id", "hub_id"]].drop_duplicates().set_index("zone_id")["hub_id"].to_dict()

    for zone_id, group in demand.groupby("zone_id"):
        series = group.set_index("date")["demand"].sort_index()
        series.index = pd.DatetimeIndex(series.index)

        forecaster = model_cls()
        forecaster.fit(series)
        predictions = forecaster.predict(horizon)

        for date, value in predictions.items():
            records.append({
                "date": date,
                "zone_id": zone_id,
                "hub_id": zone_hub[zone_id],
                "forecast_demand": round(float(value), 1),
            })

    return pd.DataFrame(records)
