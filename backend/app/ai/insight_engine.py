"""
AI Insight Engine (plan section 11).

Pipeline, enforced by structure not just convention:
  1. deterministic layer computes a structured_finding (dict)
  2. that dict (and ONLY that dict) is sent to ai.client.explain_finding
  3. both the structured_finding and the returned narrative are stored
     together, so the UI can always show the number the sentence is based on
"""
from typing import List, Dict, Any
import pandas as pd

from app.analytics import core as analytics
from app.ai.client import explain_finding


def generate_insights(df: pd.DataFrame, behavioral_scores: Dict[str, Any],
                       anomalies: List[Dict[str, Any]], recurring: List[Dict[str, Any]],
                       goal_evaluations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    insights = []

    # --- spending change insights (one per top category) ---
    breakdown = analytics.category_breakdown(df)
    for row in breakdown[:5]:
        finding = analytics.period_over_period_change(df, category=row["category"])
        if finding.get("available") and finding["trend"] in ("increasing", "decreasing"):
            narrative = explain_finding(finding, "Explain this spending trend to the user.")
            insights.append({
                "category": "spending_change",
                "structured_finding": finding,
                "narrative": narrative,
            })

    # --- anomaly insights ---
    for a in anomalies[:5]:
        narrative = explain_finding(a, "Explain why this transaction was flagged as unusual.")
        insights.append({
            "category": "anomaly",
            "structured_finding": a,
            "narrative": narrative,
        })

    # --- subscription insights ---
    for r in recurring:
        if r.get("is_active"):
            finding = {"type": "recurring_expense", **r}
            narrative = explain_finding(finding, "Summarize this recurring expense for the user in one sentence.")
            insights.append({
                "category": "subscription",
                "structured_finding": finding,
                "narrative": narrative,
            })

    # --- behavioral insight ---
    if not behavioral_scores.get("insufficient_data"):
        finding = {"type": "behavioral_profile", **{k: v for k, v in behavioral_scores.items() if not k.startswith("_")}}
        narrative = explain_finding(finding, "Summarize this user's spending behavior profile in one or two sentences.")
        insights.append({
            "category": "behavioral",
            "structured_finding": finding,
            "narrative": narrative,
        })

    # --- goal risk insights ---
    for g in goal_evaluations:
        if not g.get("feasible", True):
            finding = {"type": "goal_risk", **g}
            narrative = explain_finding(finding, "Explain this goal feasibility risk to the user, encouragingly.")
            insights.append({
                "category": "goal_risk",
                "structured_finding": finding,
                "narrative": narrative,
            })

    return insights
