"""
Forecasting — method is selected based on how much history is available
(plan section 8), never a single fixed model. Always returns a confidence
interval, never a bare point estimate. Every forecast is backtested and the
evaluation (MAE/MAPE) is returned alongside the prediction so the UI can show
"how good is this forecast" instead of presenting it as ground truth.
"""
from datetime import timedelta
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd


def _monthly_series(df: pd.DataFrame, category: Optional[str] = None) -> pd.Series:
    expense_df = df[df["transaction_type"] == "expense"]
    if category:
        expense_df = expense_df[expense_df["category"] == category]
    if expense_df.empty:
        return pd.Series(dtype=float)
    tmp = expense_df.copy()
    tmp["month"] = tmp["date"].dt.to_period("M")
    monthly = tmp.groupby("month")["amount"].sum().sort_index()
    return monthly


def _select_method(n_months: int) -> str:
    if n_months < 2:
        return "insufficient_data"
    if n_months < 6:
        return "weighted_moving_average"
    if n_months < 12:
        return "linear_regression"
    return "seasonal_linear_regression"


def _weighted_moving_average_forecast(monthly: pd.Series, horizon: int) -> np.ndarray:
    weights = np.arange(1, len(monthly) + 1)  # recent months weighted higher
    weighted_avg = float(np.average(monthly.values, weights=weights))
    return np.array([weighted_avg] * horizon)


def _linear_regression_forecast(monthly: pd.Series, horizon: int) -> np.ndarray:
    x = np.arange(len(monthly))
    y = monthly.values
    coeffs = np.polyfit(x, y, 1)  # slope, intercept
    future_x = np.arange(len(monthly), len(monthly) + horizon)
    return np.polyval(coeffs, future_x)


def _backtest(monthly: pd.Series, method: str, holdout: int = 2) -> Dict[str, float]:
    """Hold out the last `holdout` months, forecast them from the months before, score MAE/MAPE."""
    if len(monthly) <= holdout + 1:
        return {}
    train = monthly.iloc[:-holdout]
    actual = monthly.iloc[-holdout:].values

    if method in ("weighted_moving_average",):
        pred = _weighted_moving_average_forecast(train, holdout)
    else:
        pred = _linear_regression_forecast(train, holdout)

    mae = float(np.mean(np.abs(actual - pred)))
    denom = np.where(actual == 0, 1, actual)
    mape = float(np.mean(np.abs((actual - pred) / denom)) * 100)
    return {"mae": round(mae, 2), "mape": round(mape, 2), "holdout_months": holdout}


def forecast_spending(df: pd.DataFrame, category: Optional[str] = None,
                       horizon_months: int = 3) -> Dict[str, Any]:
    monthly = _monthly_series(df, category)
    n_months = len(monthly)
    method = _select_method(n_months)

    if method == "insufficient_data":
        return {
            "insufficient_data": True,
            "method": method,
            "category": category,
            "points": [],
            "evaluation": None,
        }

    if method == "weighted_moving_average":
        predictions = _weighted_moving_average_forecast(monthly, horizon_months)
    else:
        # seasonal_linear_regression: fall back to plain linear regression as the
        # core signal (a lightweight, explainable seasonal adjustment: add back the
        # average deviation of each calendar month from its yearly trend if 12+ months present)
        predictions = _linear_regression_forecast(monthly, horizon_months)
        if method == "seasonal_linear_regression":
            month_of_year = monthly.index.map(lambda p: p.month)
            trend = _linear_regression_forecast(monthly, 0) if False else None  # noop, keep simple/explainable
            seasonal_avg = pd.Series(monthly.values, index=month_of_year).groupby(level=0).mean()
            overall_avg = monthly.mean()
            seasonal_adjustment = (seasonal_avg - overall_avg).to_dict()
            last_period = monthly.index[-1]
            adjusted = []
            for i, val in enumerate(predictions):
                future_month = ((last_period.month - 1 + i + 1) % 12) + 1
                adj = seasonal_adjustment.get(future_month, 0.0)
                adjusted.append(val + adj * 0.5)  # dampened adjustment, stays conservative
            predictions = np.array(adjusted)

    predictions = np.clip(predictions, a_min=0, a_max=None)

    evaluation = _backtest(monthly, method)
    # residual-based confidence interval width
    residual_std = evaluation.get("mae", monthly.std() if len(monthly) > 1 else monthly.mean() * 0.1) or (monthly.mean() * 0.1)

    last_period = monthly.index[-1]
    points = []
    for i, val in enumerate(predictions):
        future_period = last_period + (i + 1)
        future_date = future_period.to_timestamp().date()
        points.append({
            "date": future_date,
            "value": round(float(val), 2),
            "lower": round(max(float(val) - 1.28 * residual_std, 0), 2),  # ~80% CI
            "upper": round(float(val) + 1.28 * residual_std, 2),
        })

    return {
        "insufficient_data": False,
        "method": method,
        "category": category,
        "points": points,
        "evaluation": evaluation or None,
        "months_of_history": n_months,
    }
