"""Backtesting and error metrics for forecasting models.

Rolling-origin (walk-forward) evaluation: train on history up to fold cutoff, predict
`horizon` days ahead, measure error against held-out actuals. Gives a realistic picture of
how a model would perform in live use, not just on a single train/test split.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from constraintiq.forecasting.models import Forecaster, HoltWintersForecaster, NaiveSeasonalForecaster


def mape(actual: pd.Series, predicted: pd.Series) -> float:
    """Mean absolute percentage error (%), ignoring zero-actual days."""
    mask = actual != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def mae(actual: pd.Series, predicted: pd.Series) -> float:
    """Mean absolute error (parcels/day)."""
    return float(np.mean(np.abs(actual - predicted)))


def backtest(
    model_cls: type,
    series: pd.Series,
    horizon: int,
    folds: int,
    min_train_days: int = 28,
) -> pd.DataFrame:
    """Rolling-origin backtest for a model class.

    Args:
        model_cls: Uninstantiated forecaster class (instantiated fresh each fold).
        series:    Full daily demand series, DatetimeIndex, sorted ascending.
        horizon:   Days ahead to forecast each fold.
        folds:     Number of rolling-origin folds (equally spaced across the series tail).
        min_train_days: Minimum history required before the first forecast.

    Returns:
        DataFrame with columns [fold, cutoff_date, mape_pct, mae_parcels].
    """
    n = len(series)
    if n < min_train_days + horizon:
        raise ValueError(f"Series too short: need at least {min_train_days + horizon} days.")

    # Space fold cutoffs evenly across the window where we have enough data for both
    # training and a full horizon of actuals.
    available_range = n - min_train_days - horizon
    step = max(1, available_range // folds)
    cutoffs = [min_train_days + i * step for i in range(folds)]

    rows: list[dict] = []
    for fold_idx, cutoff in enumerate(cutoffs):
        train = series.iloc[:cutoff]
        actual = series.iloc[cutoff: cutoff + horizon]

        forecaster = model_cls()
        forecaster.fit(train)
        predicted = forecaster.predict(horizon)

        actual_aligned = actual.values
        pred_aligned = predicted.values[: len(actual_aligned)]

        rows.append({
            "fold": fold_idx + 1,
            "cutoff_date": train.index[-1].date(),
            "train_days": len(train),
            "mape_pct": round(mape(pd.Series(actual_aligned), pd.Series(pred_aligned)), 2),
            "mae_parcels": round(mae(pd.Series(actual_aligned), pd.Series(pred_aligned)), 0),
        })

    return pd.DataFrame(rows)


def compare_models(
    series: pd.Series,
    horizon: int,
    folds: int = 5,
) -> pd.DataFrame:
    """Backtest both models and return a summary comparison table.

    Prints a readable table so results are immediately visible in the pipeline log.
    """
    results = {}
    for name, cls in [("naive_seasonal", NaiveSeasonalForecaster), ("holt_winters", HoltWintersForecaster)]:
        df = backtest(cls, series, horizon=horizon, folds=folds)
        results[name] = {
            "mean_mape_pct": round(df["mape_pct"].mean(), 2),
            "mean_mae_parcels": round(df["mae_parcels"].mean(), 0),
        }

    summary = pd.DataFrame(results).T
    summary.index.name = "model"
    return summary
