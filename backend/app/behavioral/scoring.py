"""
Behavioral profile scoring.

Every score is a documented formula (not a trained model) so it's fully
explainable — see plan section 6/8. Each score is normalized to 0-100.
Spending Personality is then a simple rule-based classifier on top of these
scores (also fully explainable, no black box).
"""
from typing import Dict, Any
import pandas as pd
import numpy as np

from app.analytics import core as analytics


def _clip01to100(x: float) -> float:
    return float(np.clip(x, 0, 100))


def compute_behavioral_scores(df: pd.DataFrame, min_transactions: int = 15) -> Dict[str, Any]:
    """
    Returns None-scores with an `insufficient_data` flag if there isn't
    enough history to compute a meaningful profile (graceful degradation,
    plan section 21).
    """
    if len(df) < min_transactions:
        return {"insufficient_data": True, "transactions_needed": min_transactions,
                "transactions_available": len(df)}

    summary = analytics.summarize(df)
    savings_rate = summary["savings_rate"]  # can be negative

    # --- savings_discipline: map savings_rate 0-30% onto 0-100, clip ---
    savings_discipline = _clip01to100((savings_rate / 30.0) * 100)

    # --- expense_stability: inverse of weekly spend volatility (coefficient of variation) ---
    volatility = analytics.spend_volatility(df)  # typically 0 (stable) to ~1.5+ (very volatile)
    expense_stability = _clip01to100(100 - (volatility * 60))

    # --- spending_consistency: inverse of day-to-day variance in daily spend ---
    expense_df = df[df["transaction_type"] == "expense"]
    if not expense_df.empty:
        daily = expense_df.groupby(expense_df["date"].dt.date)["amount"].sum()
        cov_daily = (daily.std() / daily.mean()) if daily.mean() > 0 else 0
    else:
        cov_daily = 0
    spending_consistency = _clip01to100(100 - (cov_daily * 40))

    # --- impulse_tendency: share of transactions that are "large & non-recurring-looking" ---
    if not expense_df.empty:
        cat_avg = expense_df.groupby("category")["amount"].transform("mean")
        cat_std = expense_df.groupby("category")["amount"].transform("std").fillna(0)
        is_large = expense_df["amount"] > (cat_avg + 1.5 * cat_std)
        impulse_share = is_large.sum() / len(expense_df)
    else:
        impulse_share = 0
    impulse_tendency = _clip01to100(impulse_share * 300)  # scale so ~33% large txns = 100

    # --- weekend_spending_tendency: weekend avg daily / weekday avg daily, normalized ---
    split = analytics.weekday_weekend_split(df)
    if split["weekday_avg_daily"] > 0:
        ratio = split["weekend_avg_daily"] / split["weekday_avg_daily"]
    else:
        ratio = 1.0
    # ratio of 1.0 (equal) -> 50, ratio of 2.5+ -> 100
    weekend_spending_tendency = _clip01to100(((ratio - 1.0) / 1.5) * 50 + 50)

    # subscription_burden is intentionally supplied by the API/service layer because
    # it depends on recurring-expense detection, which belongs outside this pure scorer.

    # --- category_concentration: from analytics (Herfindahl 0-1) scaled to 0-100 ---
    concentration_index = analytics.category_concentration_index(df)
    category_concentration = _clip01to100(concentration_index * 100 * 2.5)  # HHI rarely exceeds ~0.4 in practice

    return {
        "insufficient_data": False,
        "savings_discipline": round(savings_discipline, 1),
        "expense_stability": round(expense_stability, 1),
        "spending_consistency": round(spending_consistency, 1),
        "impulse_tendency": round(impulse_tendency, 1),
        "weekend_spending_tendency": round(weekend_spending_tendency, 1),
        "category_concentration": round(category_concentration, 1),
        "_raw": {
            "savings_rate": savings_rate,
            "volatility": round(volatility, 3),
            "cov_daily": round(float(cov_daily), 3) if not pd.isna(cov_daily) else 0,
            "impulse_share": round(float(impulse_share), 3),
            "weekend_ratio": round(float(ratio), 3),
            "concentration_index": concentration_index,
        },
    }


def classify_personality(scores: Dict[str, Any]) -> str:
    """
    Rule-based classifier (decision table, not ML) — fully explainable per
    plan section 9. Order matters: first matching rule wins.
    """
    if scores.get("insufficient_data"):
        return "Developing Profile"

    sub = scores.get("subscription_burden", 0)
    weekend = scores["weekend_spending_tendency"]
    impulse = scores["impulse_tendency"]
    savings = scores["savings_discipline"]
    stability = scores["expense_stability"]

    if sub > 70:
        return "Subscription Heavy"
    if weekend > 70 and impulse < 50:
        return "Weekend Spender"
    if impulse > 70:
        return "Impulse Buyer"
    if savings > 60 and stability > 60:
        return "Balanced Planner"
    return "Developing Profile"


def goal_readiness_score(months_to_target: float, required_monthly_savings: float,
                          actual_monthly_savings: float) -> float:
    """
    100 = comfortably on track, 0 = required savings far exceeds actual.
    Used by goals module; kept here so all behavioral-style scoring formulas
    live in one place.
    """
    if required_monthly_savings <= 0:
        return 100.0
    if actual_monthly_savings <= 0:
        return 0.0
    ratio = actual_monthly_savings / required_monthly_savings
    return round(_clip01to100(ratio * 100), 1)
