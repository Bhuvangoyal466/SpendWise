"""
Anomaly detection — real ML (Isolation Forest), trained per-user on that
user's own history, with a statistical fallback for users below the minimum
data threshold (graceful degradation, plan section 21).

The model's job stops at score + feature attribution. It never generates
explanation text — that's the AI insight engine's job, and it only ever
receives this structured `reason` dict, never raw transactions.
"""
from typing import List, Dict, Any
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest

MIN_TRANSACTIONS_FOR_ML = 40


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-transaction features:
      - amount_zscore: how many std devs this amount is from its category's mean
      - day_of_week
      - category_frequency: how common this category is overall (novelty signal)
      - merchant_novelty: 1 if this is the first time we've seen this merchant
      - deviation_from_category_rolling_avg
    """
    expense_df = df[df["transaction_type"] == "expense"].copy().sort_values("date")
    if expense_df.empty:
        return expense_df

    cat_mean = expense_df.groupby("category")["amount"].transform("mean")
    cat_std = expense_df.groupby("category")["amount"].transform("std").fillna(1).replace(0, 1)
    expense_df["amount_zscore"] = (expense_df["amount"] - cat_mean) / cat_std

    expense_df["day_of_week"] = expense_df["date"].dt.weekday

    cat_counts = expense_df["category"].value_counts(normalize=True)
    expense_df["category_frequency"] = expense_df["category"].map(cat_counts)

    seen_merchants = set()
    novelty = []
    for m in expense_df["merchant"]:
        novelty.append(1 if m not in seen_merchants else 0)
        seen_merchants.add(m)
    expense_df["merchant_novelty"] = novelty

    expense_df["rolling_cat_avg"] = (
        expense_df.groupby("category")["amount"]
        .transform(lambda s: s.expanding().mean().shift(1).fillna(s.mean()))
    )
    expense_df["deviation_from_rolling_avg"] = expense_df["amount"] - expense_df["rolling_cat_avg"]

    return expense_df


def detect_anomalies(df: pd.DataFrame, contamination: float = 0.05) -> List[Dict[str, Any]]:
    """
    Returns a list of dicts: {index_in_df, anomaly_score, method, reason}
    Caller (API layer) is responsible for mapping back to transaction ids.
    """
    featured = _build_features(df)
    if featured.empty:
        return []

    if len(featured) < MIN_TRANSACTIONS_FOR_ML:
        return _statistical_fallback(featured)

    feature_cols = ["amount_zscore", "day_of_week", "category_frequency",
                     "merchant_novelty", "deviation_from_rolling_avg"]
    X = featured[feature_cols].fillna(0).values

    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=42)
    model.fit(X)
    raw_scores = model.decision_function(X)  # higher = more normal
    predictions = model.predict(X)  # -1 = anomaly, 1 = normal

    # Normalize raw_scores to a 0-1 "anomaly score" (invert so higher = more anomalous)
    min_s, max_s = raw_scores.min(), raw_scores.max()
    span = (max_s - min_s) or 1.0
    anomaly_scores = 1 - ((raw_scores - min_s) / span)

    results = []
    for i, (pred, score) in enumerate(zip(predictions, anomaly_scores)):
        if pred == -1:
            row = featured.iloc[i]
            reason = _explain_row(row)
            results.append({
                "transaction_index": featured.index[i],
                "anomaly_score": round(float(score), 3),
                "method": "isolation_forest",
                "reason": reason,
            })
    return results


def _explain_row(row: pd.Series) -> Dict[str, Any]:
    """Pick the single most extreme feature as the human-facing reason."""
    candidates = {
        "amount_zscore": abs(row.get("amount_zscore", 0)),
        "merchant_novelty": row.get("merchant_novelty", 0) * 2,  # weight novelty a bit lower
        "deviation_from_rolling_avg": abs(row.get("deviation_from_rolling_avg", 0)) / max(row.get("rolling_cat_avg", 1), 1),
    }
    top_feature = max(candidates, key=candidates.get)
    if top_feature == "amount_zscore":
        return {
            "feature": "amount_zscore",
            "value": round(float(row["amount_zscore"]), 2),
            "message": f"Amount is {round(float(row['amount_zscore']), 1)} standard deviations from the typical "
                       f"{row['category']} transaction.",
        }
    if top_feature == "merchant_novelty":
        return {
            "feature": "merchant_novelty",
            "value": 1,
            "message": f"First transaction seen at merchant '{row['merchant']}'.",
        }
    return {
        "feature": "deviation_from_rolling_avg",
        "value": round(float(row["deviation_from_rolling_avg"]), 2),
        "message": f"₹{round(float(row['deviation_from_rolling_avg']), 2)} above the recent average for "
                   f"{row['category']}.",
    }


def _statistical_fallback(featured: pd.DataFrame, z_threshold: float = 3.0) -> List[Dict[str, Any]]:
    """Simple per-category z-score rule, used when there isn't enough data for Isolation Forest."""
    results = []
    for idx, row in featured.iterrows():
        z = row.get("amount_zscore", 0)
        if abs(z) >= z_threshold:
            results.append({
                "transaction_index": idx,
                "anomaly_score": round(min(abs(float(z)) / 6.0, 1.0), 3),
                "method": "statistical",
                "reason": {
                    "feature": "amount_zscore",
                    "value": round(float(z), 2),
                    "message": f"Amount is {round(float(z), 1)} standard deviations from the typical "
                               f"{row['category']} transaction.",
                },
            })
    return results
