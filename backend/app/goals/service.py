"""
Financial goals — deterministic feasibility math (plan section 10).
Feasibility compares required savings against the *forecasted* future
savings rate (not just historical average) since that's the more honest
predictive answer, and connects directly into the simulator.
"""
from datetime import date
from typing import Dict, Any, Optional


def evaluate_goal(target_amount: float, current_saved: float, target_date: date,
                   today: date, actual_avg_monthly_savings: float,
                   forecasted_monthly_savings: Optional[float] = None) -> Dict[str, Any]:
    remaining = max(target_amount - current_saved, 0)
    days_left = (target_date - today).days
    months_left = max(days_left / 30.44, 0.001)

    required_monthly = remaining / months_left if months_left > 0 else remaining

    # Prefer the forecast if available (more forward-looking); fall back to historical average.
    basis_savings = forecasted_monthly_savings if forecasted_monthly_savings is not None else actual_avg_monthly_savings
    basis_label = "forecast" if forecasted_monthly_savings is not None else "historical_average"

    if days_left <= 0:
        feasible = current_saved >= target_amount
        note = "Target date has passed." if not feasible else "Goal already reached."
    elif basis_savings <= 0:
        feasible = False
        note = f"Required ₹{required_monthly:,.2f}/month but current savings trend is at or below zero."
    else:
        feasible = basis_savings >= required_monthly
        if feasible:
            note = (f"At your {basis_label} pace of ₹{basis_savings:,.2f}/month, you're on track "
                     f"(need ₹{required_monthly:,.2f}/month).")
        else:
            shortfall = required_monthly - basis_savings
            note = (f"At your {basis_label} pace of ₹{basis_savings:,.2f}/month, you're short by "
                     f"₹{shortfall:,.2f}/month of the ₹{required_monthly:,.2f}/month needed.")

    return {
        "remaining_amount": round(remaining, 2),
        "months_left": round(months_left, 2),
        "required_monthly_savings": round(required_monthly, 2),
        "feasible": feasible,
        "feasibility_note": note,
        "basis": basis_label,
    }
