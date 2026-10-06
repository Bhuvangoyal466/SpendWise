from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import User, Goal
from app.schemas.schemas import GoalCreate, GoalOut
from app.api.auth import get_current_user
from app.api.deps import load_transactions_for_user
from app.analytics.core import transactions_to_df, monthly_trend
from app.ml.forecast import forecast_spending
from app.goals import service as goals_service

router = APIRouter(prefix="/api/goals", tags=["goals"])


def _actual_avg_monthly_savings(df) -> float:
    trend = monthly_trend(df)
    if not trend:
        return 0.0
    nets = [m["net"] for m in trend]
    return sum(nets) / len(nets)


def _forecasted_monthly_savings(df) -> float:
    income_forecast = forecast_spending(df, category=None, horizon_months=1)  # note: total expense forecast below
    expense_forecast = forecast_spending(df, category=None, horizon_months=1)
    if expense_forecast.get("insufficient_data") or not expense_forecast["points"]:
        return None
    # crude but explainable: forecasted expense vs. recent average income
    trend = monthly_trend(df)
    avg_income = sum(m["income"] for m in trend) / len(trend) if trend else 0
    forecasted_expense = expense_forecast["points"][0]["value"]
    return round(avg_income - forecasted_expense, 2)


def _to_out(g: Goal, df) -> GoalOut:
    forecasted = _forecasted_monthly_savings(df)
    actual_avg = _actual_avg_monthly_savings(df)
    evaluation = goals_service.evaluate_goal(
        target_amount=g.target_amount, current_saved=g.current_saved, target_date=g.target_date,
        today=date.today(), actual_avg_monthly_savings=actual_avg, forecasted_monthly_savings=forecasted,
    )
    return GoalOut(
        id=g.id, name=g.name, target_amount=g.target_amount, current_saved=g.current_saved,
        target_date=g.target_date, remaining_amount=evaluation["remaining_amount"],
        months_left=evaluation["months_left"], required_monthly_savings=evaluation["required_monthly_savings"],
        feasible=evaluation["feasible"], feasibility_note=evaluation["feasibility_note"],
    )


@router.get("", response_model=List[GoalOut])
def list_goals(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transactions = load_transactions_for_user(db, user.id)
    df = transactions_to_df(transactions)
    goals = db.query(Goal).filter(Goal.user_id == user.id).all()
    return [_to_out(g, df) for g in goals]


@router.post("", response_model=GoalOut)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    g = Goal(user_id=user.id, name=payload.name, target_amount=payload.target_amount,
              current_saved=payload.current_saved, target_date=payload.target_date)
    db.add(g)
    db.commit()
    db.refresh(g)
    transactions = load_transactions_for_user(db, user.id)
    df = transactions_to_df(transactions)
    return _to_out(g, df)


@router.delete("/{goal_id}")
def delete_goal(goal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    g = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(g)
    db.commit()
    return {"status": "deleted"}
