"""
Subscription / recurring expense detection (plan section 9).

Guardrail from the brief, enforced here structurally: this module only ever
outputs *spending facts* (amount, frequency, trend). It never touches or
infers actual service usage, because there's no usage data to justify such a
claim — the schema doesn't even have a field for it.
"""
from typing import List, Dict, Any
import pandas as pd
import numpy as np

FREQUENCY_BUCKETS = {
    "weekly": (5, 9),
    "monthly": (25, 35),
    "annual": (350, 380),
}


def detect_recurring(df: pd.DataFrame, min_occurrences: int = 3,
                      amount_tolerance: float = 0.10) -> List[Dict[str, Any]]:
    expense_df = df[df["transaction_type"] == "expense"]
    if expense_df.empty or "merchant" not in expense_df:
        return []

    results = []
    for merchant, group in expense_df.groupby("merchant"):
        group = group.sort_values("date")
        if len(group) < min_occurrences:
            continue

        # check amount consistency
        mean_amount = group["amount"].mean()
        if mean_amount == 0:
            continue
        amount_cv = group["amount"].std() / mean_amount if len(group) > 1 else 0
        amount_consistent = amount_cv <= amount_tolerance

        # check interval consistency
        intervals = group["date"].diff().dt.days.dropna()
        if intervals.empty:
            continue
        mean_interval = intervals.mean()

        frequency_label = None
        for label, (lo, hi) in FREQUENCY_BUCKETS.items():
            if lo <= mean_interval <= hi:
                frequency_label = label
                break
        if frequency_label is None:
            continue  # doesn't look periodic

        interval_cv = (intervals.std() / mean_interval) if mean_interval > 0 and len(intervals) > 1 else 0
        interval_consistent = interval_cv <= 0.35

        # confidence: weighted combination of repetitions, amount consistency, interval consistency
        repetitions_score = min(len(group) / 6.0, 1.0)
        amount_score = max(0.0, 1 - amount_cv)
        interval_score = max(0.0, 1 - interval_cv)
        confidence = round(float(0.4 * repetitions_score + 0.3 * amount_score + 0.3 * interval_score), 2)

        if not (amount_consistent or interval_consistent):
            continue

        category = group["category"].mode().iloc[0] if "category" in group and not group["category"].mode().empty else None

        results.append({
            "merchant": merchant,
            "category": category,
            "average_amount": round(float(mean_amount), 2),
            "frequency": frequency_label,
            "confidence_score": confidence,
            "first_seen": group["date"].min().date(),
            "last_seen": group["date"].max().date(),
            "occurrences": len(group),
            "is_active": (group["date"].max() >= (expense_df["date"].max() - pd.Timedelta(days=mean_interval * 1.5))),
        })

    return sorted(results, key=lambda r: r["average_amount"], reverse=True)


def monthly_equivalent(amount: float, frequency: str) -> float:
    factor = {"weekly": 4.33, "monthly": 1.0, "annual": 1 / 12}.get(frequency, 1.0)
    return round(amount * factor, 2)


def subscription_burden_pct(recurring: List[Dict[str, Any]], monthly_income: float) -> float:
    """Feeds the `subscription_burden` behavioral score."""
    if monthly_income <= 0:
        return 0.0
    total_monthly = sum(monthly_equivalent(r["average_amount"], r["frequency"])
                         for r in recurring if r["is_active"])
    return round(min(total_monthly / monthly_income * 100, 100), 1)
