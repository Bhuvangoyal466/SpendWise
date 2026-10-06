"""
Deterministic analytics layer.

Nothing in this file calls ML or the LLM. Every other intelligent module
(behavioral scoring, anomaly detection, forecasting, simulation) is allowed
to depend on these functions, but not the other way around. This is what
makes the dashboard fully correct even when there isn't enough data for the
ML-driven features (see MIN_* thresholds used elsewhere).
"""
from datetime import date, timedelta
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np


def transactions_to_df(transactions: List[dict]) -> pd.DataFrame:
    """
    transactions: list of dicts with keys
      date, amount, transaction_type, category, merchant
    amount is stored positive; we create a signed `signed_amount` column
    (negative = expense) which is what most aggregate math wants.
    """
    if not transactions:
        return pd.DataFrame(columns=[
            "date", "amount", "transaction_type", "category", "merchant", "signed_amount"
        ])
    df = pd.DataFrame(transactions)
    # Accept both the normalized API shape (`category`) and the synthetic
    # generator/import shape (`category_name`). Keeping this boundary
    # tolerant prevents every downstream analytics module from having to
    # know where the transaction originated.
    if "category" not in df.columns and "category_name" in df.columns:
        df["category"] = df["category_name"]
    if "category" not in df.columns:
        df["category"] = "Uncategorized"
    if "merchant" not in df.columns:
        df["merchant"] = None
    df["date"] = pd.to_datetime(df["date"])
    df["signed_amount"] = np.where(
        df["transaction_type"] == "expense", -df["amount"], df["amount"]
    )
    return df


def summarize(df: pd.DataFrame, start: Optional[date] = None, end: Optional[date] = None) -> Dict[str, Any]:
    """Core dashboard aggregates: income, expenses, savings, savings rate, etc."""
    if start:
        df = df[df["date"] >= pd.to_datetime(start)]
    if end:
        df = df[df["date"] <= pd.to_datetime(end)]

    income = df.loc[df["transaction_type"] == "income", "amount"].sum()
    expenses = df.loc[df["transaction_type"] == "expense", "amount"].sum()
    net_savings = income - expenses
    savings_rate = (net_savings / income * 100) if income > 0 else 0.0

    expense_df = df[df["transaction_type"] == "expense"]
    avg_txn = expense_df["amount"].mean() if len(expense_df) else 0.0

    return {
        "total_income": round(float(income), 2),
        "total_expenses": round(float(expenses), 2),
        "net_savings": round(float(net_savings), 2),
        "savings_rate": round(float(savings_rate), 2),
        "average_transaction": round(float(avg_txn), 2) if not pd.isna(avg_txn) else 0.0,
    }


def top_categories(df: pd.DataFrame, n: int = 5) -> List[Dict[str, Any]]:
    expense_df = df[df["transaction_type"] == "expense"]
    if expense_df.empty:
        return []
    total = expense_df["amount"].sum()
    grouped = (
        expense_df.groupby("category")["amount"]
        .agg(total="sum", count="count", average="mean")
        .reset_index()
        .sort_values("total", ascending=False)
        .head(n)
    )
    grouped["pct_of_total"] = (grouped["total"] / total * 100).round(2)
    return grouped.round(2).to_dict(orient="records")


def top_merchants(df: pd.DataFrame, n: int = 5) -> List[Dict[str, Any]]:
    expense_df = df[df["transaction_type"] == "expense"]
    if expense_df.empty or "merchant" not in expense_df:
        return []
    grouped = (
        expense_df.groupby("merchant")["amount"]
        .agg(total="sum", count="count", average="mean", largest="max")
        .reset_index()
        .sort_values("total", ascending=False)
        .head(n)
    )
    return grouped.round(2).to_dict(orient="records")


def category_breakdown(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Full per-category stats — section 7 of the plan (category intelligence)."""
    expense_df = df[df["transaction_type"] == "expense"]
    if expense_df.empty:
        return []
    total = expense_df["amount"].sum()
    grouped = expense_df.groupby("category")["amount"].agg(
        total="sum", average="mean", count="count", largest_transaction="max"
    ).reset_index()
    grouped["pct_of_total"] = (grouped["total"] / total * 100).round(2)
    return grouped.round(2).to_dict(orient="records")


def monthly_trend(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Monthly income vs expenses — feeds the dashboard trend chart and forecasting input."""
    if df.empty:
        return []
    tmp = df.copy()
    tmp["month"] = tmp["date"].dt.to_period("M").astype(str)
    grouped = tmp.groupby(["month", "transaction_type"])["amount"].sum().unstack(fill_value=0)
    grouped = grouped.reset_index()
    for col in ("income", "expense"):
        if col not in grouped:
            grouped[col] = 0.0
    grouped["net"] = grouped["income"] - grouped["expense"]
    return grouped.round(2).to_dict(orient="records")


def period_over_period_change(df: pd.DataFrame, category: Optional[str] = None,
                               window_days: int = 30) -> Dict[str, Any]:
    """
    Compares trailing `window_days` against the prior `window_days` window.
    Used both for the dashboard trend indicators and as the structured
    finding fed to the AI insight engine (never let the LLM compute this).
    """
    expense_df = df[df["transaction_type"] == "expense"]
    if category:
        expense_df = expense_df[expense_df["category"] == category]
    if expense_df.empty:
        return {"available": False}

    latest_date = expense_df["date"].max()
    recent_start = latest_date - pd.Timedelta(days=window_days)
    prior_start = recent_start - pd.Timedelta(days=window_days)

    recent = expense_df[(expense_df["date"] > recent_start) & (expense_df["date"] <= latest_date)]["amount"].sum()
    prior = expense_df[(expense_df["date"] > prior_start) & (expense_df["date"] <= recent_start)]["amount"].sum()

    if prior == 0:
        pct_change = None
    else:
        pct_change = round((recent - prior) / prior * 100, 2)

    if pct_change is None:
        trend = "new" if recent > 0 else "none"
    elif pct_change > 10:
        trend = "increasing"
    elif pct_change < -10:
        trend = "decreasing"
    else:
        trend = "stable"

    return {
        "available": True,
        "category": category or "total",
        "prior_period_total": round(float(prior), 2),
        "recent_period_total": round(float(recent), 2),
        "pct_change": pct_change,
        "trend": trend,
    }


def spend_volatility(df: pd.DataFrame) -> float:
    """
    Coefficient of variation of weekly total spend. Feeds `expense_stability`
    behavioral score (inverse relationship: high volatility -> low stability).
    """
    expense_df = df[df["transaction_type"] == "expense"]
    if expense_df.empty:
        return 0.0
    tmp = expense_df.copy()
    tmp["week"] = tmp["date"].dt.to_period("W").astype(str)
    weekly = tmp.groupby("week")["amount"].sum()
    if len(weekly) < 2 or weekly.mean() == 0:
        return 0.0
    return float(weekly.std() / weekly.mean())


def weekday_weekend_split(df: pd.DataFrame) -> Dict[str, float]:
    expense_df = df[df["transaction_type"] == "expense"]
    if expense_df.empty:
        return {"weekday_avg_daily": 0.0, "weekend_avg_daily": 0.0}
    tmp = expense_df.copy()
    tmp["is_weekend"] = tmp["date"].dt.weekday >= 5
    tmp["day"] = tmp["date"].dt.date

    daily = tmp.groupby(["day", "is_weekend"])["amount"].sum().reset_index()
    weekday_avg = daily.loc[~daily["is_weekend"], "amount"].mean() if (~daily["is_weekend"]).any() else 0.0
    weekend_avg = daily.loc[daily["is_weekend"], "amount"].mean() if daily["is_weekend"].any() else 0.0

    return {
        "weekday_avg_daily": round(float(weekday_avg) if not pd.isna(weekday_avg) else 0.0, 2),
        "weekend_avg_daily": round(float(weekend_avg) if not pd.isna(weekend_avg) else 0.0, 2),
    }


def heatmap_data(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Day-of-week x week-of-year spend intensity, for the dashboard heatmap."""
    expense_df = df[df["transaction_type"] == "expense"]
    if expense_df.empty:
        return []
    tmp = expense_df.copy()
    tmp["weekday"] = tmp["date"].dt.day_name()
    tmp["week"] = tmp["date"].dt.strftime("%Y-W%U")
    grouped = tmp.groupby(["week", "weekday"])["amount"].sum().reset_index()
    return grouped.round(2).to_dict(orient="records")


def category_concentration_index(df: pd.DataFrame) -> float:
    """
    Herfindahl-style concentration index (sum of squared category shares).
    0 = perfectly spread out, 1 = all spending in one category.
    Feeds the `category_concentration` behavioral score.
    """
    expense_df = df[df["transaction_type"] == "expense"]
    if expense_df.empty:
        return 0.0
    totals = expense_df.groupby("category")["amount"].sum()
    total = totals.sum()
    if total == 0:
        return 0.0
    shares = totals / total
    return round(float((shares ** 2).sum()), 4)
