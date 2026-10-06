"""
The Financial What-If Simulator + Financial Time Machine (plan sections
13-14) — the hero feature. This is the ONE engine both the forward simulator
UI and the Time Machine UI call; the only difference is which baseline gets
built (forward-looking vs. a real historical period).

Design rule: this module reuses app.analytics and app.ml.forecast for its
baseline — it never recomputes spending logic independently, so a
simulation is always consistent with what the dashboard shows.

Everything returned by run_time_machine() must be treated by the API/UI
layer as hypothetical and labeled as such — this module does not label it
for you; the caller is responsible for the "Hypothetical — not what
actually happened" banner per plan section 17.
"""
from datetime import date
from typing import Dict, Any, List, Optional
import pandas as pd

from app.analytics import core as analytics
from app.ml import forecast as forecasting


def _build_forward_baseline(df: pd.DataFrame, horizon_months: int) -> Dict[str, Any]:
    """
    Baseline = actual recent income + forecasted spending per category +
    detected recurring expenses, as of "today" (plan section 13).
    """
    summary = analytics.summarize(df)
    breakdown = analytics.category_breakdown(df)

    # Use last 3 months as the "current monthly rate" reference
    latest_date = df["date"].max()
    recent_start = latest_date - pd.Timedelta(days=90)
    recent_df = df[df["date"] > recent_start]
    recent_summary = analytics.summarize(recent_df)
    recent_breakdown = {row["category"]: row["total"] / 3 for row in analytics.category_breakdown(recent_df)}

    monthly_income = recent_summary["total_income"] / 3 if recent_summary["total_income"] else 0
    monthly_expense_by_category = recent_breakdown

    return {
        "source": "actual_recent_3_months_average",
        "monthly_income": round(monthly_income, 2),
        "monthly_expense_by_category": {k: round(v, 2) for k, v in monthly_expense_by_category.items()},
        "monthly_total_expense": round(sum(monthly_expense_by_category.values()), 2),
        "horizon_months": horizon_months,
    }


def _build_time_machine_baseline(df: pd.DataFrame, start: date, end: date) -> Dict[str, Any]:
    """Baseline built from a REAL historical period, for retroactive what-if comparison."""
    period_df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
    summary = analytics.summarize(period_df)
    breakdown = {row["category"]: row["total"] for row in analytics.category_breakdown(period_df)}
    n_months = max((end - start).days / 30.44, 1)

    return {
        "source": f"actual_history_{start}_{end}",
        "period_income": summary["total_income"],
        "expense_by_category": breakdown,
        "period_total_expense": summary["total_expenses"],
        "actual_net_savings": summary["net_savings"],
        "n_months": round(n_months, 2),
    }


def _apply_scenario_to_categories(category_amounts: Dict[str, float],
                                   pct_changes: Dict[str, float]) -> Dict[str, float]:
    result = {}
    for category, amount in category_amounts.items():
        pct = pct_changes.get(category, 0.0)
        result[category] = round(amount * (1 + pct), 2)
    return result


def run_forward_simulation(df: pd.DataFrame, assumptions: Dict[str, Any],
                            horizon_months: int = 6) -> Dict[str, Any]:
    baseline = _build_forward_baseline(df, horizon_months)

    category_pct_changes = assumptions.get("category_pct_changes", {})
    income_pct_change = assumptions.get("income_pct_change", 0.0)
    disable_merchants = assumptions.get("disable_recurring_merchants", [])

    simulated_categories = _apply_scenario_to_categories(
        baseline["monthly_expense_by_category"], category_pct_changes
    )
    simulated_income = round(baseline["monthly_income"] * (1 + income_pct_change), 2)
    simulated_total_expense = round(sum(simulated_categories.values()), 2)
    simulated_net_savings = round(simulated_income - simulated_total_expense, 2)
    simulated_savings_rate = round((simulated_net_savings / simulated_income * 100) if simulated_income else 0, 2)

    baseline_net_savings = round(baseline["monthly_income"] - baseline["monthly_total_expense"], 2)
    baseline_savings_rate = round((baseline_net_savings / baseline["monthly_income"] * 100)
                                   if baseline["monthly_income"] else 0, 2)

    additional_monthly_savings = round(simulated_net_savings - baseline_net_savings, 2)

    # trajectory: project both paths forward for the horizon
    trajectory = []
    for m in range(1, horizon_months + 1):
        trajectory.append({
            "month": m,
            "baseline_cumulative_savings": round(baseline_net_savings * m, 2),
            "simulated_cumulative_savings": round(simulated_net_savings * m, 2),
        })

    return {
        "baseline": {
            "monthly_income": baseline["monthly_income"],
            "monthly_expense_total": baseline["monthly_total_expense"],
            "monthly_expense_by_category": baseline["monthly_expense_by_category"],
            "net_savings": baseline_net_savings,
            "savings_rate": baseline_savings_rate,
        },
        "simulated": {
            "monthly_income": simulated_income,
            "monthly_expense_total": simulated_total_expense,
            "monthly_expense_by_category": simulated_categories,
            "net_savings": simulated_net_savings,
            "savings_rate": simulated_savings_rate,
        },
        "delta": {
            "additional_monthly_savings": additional_monthly_savings,
            "additional_savings_over_horizon": round(additional_monthly_savings * horizon_months, 2),
            "savings_rate_change": round(simulated_savings_rate - baseline_savings_rate, 2),
        },
        "trajectory": trajectory,
        "assumptions_used": assumptions,
        "source_baseline": baseline["source"],
    }


def run_time_machine_simulation(df: pd.DataFrame, assumptions: Dict[str, Any],
                                 start: date, end: date) -> Dict[str, Any]:
    """
    Retroactive simulation: 'what if this hypothetical strategy had applied
    during this real historical period?' All outputs here are hypothetical
    by construction — the caller must label them as such in the UI.
    """
    baseline = _build_time_machine_baseline(df, start, end)

    category_pct_changes = assumptions.get("category_pct_changes", {})
    income_pct_change = assumptions.get("income_pct_change", 0.0)

    simulated_categories = _apply_scenario_to_categories(baseline["expense_by_category"], category_pct_changes)
    simulated_income = round(baseline["period_income"] * (1 + income_pct_change), 2)
    simulated_total_expense = round(sum(simulated_categories.values()), 2)
    simulated_net_savings = round(simulated_income - simulated_total_expense, 2)

    additional_savings = round(simulated_net_savings - baseline["actual_net_savings"], 2)

    return {
        "baseline": {
            "period_start": str(start),
            "period_end": str(end),
            "actual_income": baseline["period_income"],
            "actual_expense_total": baseline["period_total_expense"],
            "actual_expense_by_category": baseline["expense_by_category"],
            "actual_net_savings": baseline["actual_net_savings"],
        },
        "simulated": {
            "hypothetical_income": simulated_income,
            "hypothetical_expense_total": simulated_total_expense,
            "hypothetical_expense_by_category": simulated_categories,
            "hypothetical_net_savings": simulated_net_savings,
        },
        "delta": {
            "additional_savings_over_period": additional_savings,
        },
        "trajectory": [
            {"label": "Actual", "net_savings": baseline["actual_net_savings"]},
            {"label": "Hypothetical", "net_savings": simulated_net_savings},
        ],
        "assumptions_used": assumptions,
        "disclaimer": "Hypothetical — this is not what actually happened. Computed by re-applying your "
                       "chosen changes to real historical spending data.",
    }


def apply_goal_impact(simulation_result: Dict[str, Any], required_monthly_savings: float) -> Dict[str, Any]:
    """Connects a forward simulation's outcome to goal feasibility (ties sections 10 + 13 together)."""
    simulated_savings = simulation_result["simulated"]["net_savings"]
    baseline_savings = simulation_result["baseline"]["net_savings"]
    return {
        "required_monthly_savings": required_monthly_savings,
        "baseline_meets_goal": baseline_savings >= required_monthly_savings,
        "simulated_meets_goal": simulated_savings >= required_monthly_savings,
        "note": (
            "This scenario would make your goal feasible." if simulated_savings >= required_monthly_savings
            and baseline_savings < required_monthly_savings else
            "This scenario does not change whether your goal is feasible."
            if (simulated_savings >= required_monthly_savings) == (baseline_savings >= required_monthly_savings)
            else "This scenario would make your goal infeasible."
        ),
    }
