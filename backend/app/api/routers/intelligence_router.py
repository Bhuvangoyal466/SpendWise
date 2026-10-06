"""
Groups the behavioral / anomaly / forecast / subscription endpoints — each
is a thin HTTP layer over the corresponding module in app/behavioral,
app/ml, app/subscriptions. No business logic lives in this file.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import User, Transaction
from app.api.auth import get_current_user
from app.api.deps import load_transactions_for_user
from app.analytics.core import transactions_to_df, summarize
from app.behavioral import scoring as behavioral
from app.ml import anomaly as anomaly_ml
from app.ml import forecast as forecast_ml
from app.subscriptions import detector as subs
from app.schemas.schemas import BehavioralScoreOut, AnomalyOut, ForecastOut, RecurringExpenseOut

router = APIRouter(prefix="/api", tags=["intelligence"])


def _recurring_for_user(db: Session, user: User, df):
    return subs.detect_recurring(df)


@router.get("/behavioral/profile", response_model=BehavioralScoreOut)
def behavioral_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transactions = load_transactions_for_user(db, user.id)
    df = transactions_to_df(transactions)
    scores = behavioral.compute_behavioral_scores(df)

    if scores.get("insufficient_data"):
        return BehavioralScoreOut(
            savings_discipline=0, expense_stability=0, spending_consistency=0,
            impulse_tendency=0, weekend_spending_tendency=0, subscription_burden=0,
            category_concentration=0, goal_readiness=0, personality_label="Developing Profile",
            explanation={"status": f"Need at least {scores['transactions_needed']} transactions "
                                    f"({scores['transactions_available']} available)."},
        )

    recurring = _recurring_for_user(db, user, df)
    summary = summarize(df)
    monthly_income = summary["total_income"] / max(len(df["date"].dt.to_period("M").unique()), 1) if not df.empty else 0
    sub_burden = subs.subscription_burden_pct(recurring, monthly_income) if monthly_income else 0.0
    scores["subscription_burden"] = sub_burden

    personality = behavioral.classify_personality(scores)

    return BehavioralScoreOut(
        savings_discipline=scores["savings_discipline"],
        expense_stability=scores["expense_stability"],
        spending_consistency=scores["spending_consistency"],
        impulse_tendency=scores["impulse_tendency"],
        weekend_spending_tendency=scores["weekend_spending_tendency"],
        subscription_burden=scores["subscription_burden"],
        category_concentration=scores["category_concentration"],
        goal_readiness=0,  # populated when a goal exists; see goals router
        personality_label=personality,
        explanation={
            "savings_discipline": f"Savings rate of {scores['_raw']['savings_rate']}% mapped to a 0-100 scale.",
            "expense_stability": f"Weekly spend volatility (coefficient of variation) = {scores['_raw']['volatility']}.",
            "impulse_tendency": f"{round(scores['_raw']['impulse_share']*100,1)}% of transactions were unusually large for their category.",
            "weekend_spending_tendency": f"Weekend/weekday daily spend ratio = {scores['_raw']['weekend_ratio']}.",
            "category_concentration": f"Herfindahl concentration index = {scores['_raw']['concentration_index']}.",
        },
    )


@router.get("/anomalies", response_model=List[AnomalyOut])
def get_anomalies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transactions = load_transactions_for_user(db, user.id)
    df = transactions_to_df(transactions)
    if df.empty:
        return []

    # need to keep the original transaction id mapped to df row index
    raw_results = anomaly_ml.detect_anomalies(df)

    out = []
    for r in raw_results:
        idx = r["transaction_index"]
        row = df.loc[idx]
        out.append(AnomalyOut(
            id=f"anomaly-{row['id']}", transaction_id=row["id"], date=row["date"].date(),
            amount=row["amount"], merchant=row.get("merchant"), category=row.get("category"),
            anomaly_score=r["anomaly_score"], method=r["method"], reason=r["reason"],
        ))
    return sorted(out, key=lambda a: a.anomaly_score, reverse=True)


@router.get("/forecast", response_model=ForecastOut)
def get_forecast(category: Optional[str] = None, horizon_months: int = 3,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transactions = load_transactions_for_user(db, user.id)
    df = transactions_to_df(transactions)
    result = forecast_ml.forecast_spending(df, category=category, horizon_months=horizon_months)

    if result["insufficient_data"]:
        return ForecastOut(method=result["method"], horizon_days=horizon_months * 30,
                            category=category, points=[], evaluation=None, insufficient_data=True)

    return ForecastOut(
        method=result["method"], horizon_days=horizon_months * 30, category=category,
        points=result["points"], evaluation=result["evaluation"], insufficient_data=False,
    )


@router.get("/subscriptions", response_model=List[RecurringExpenseOut])
def get_subscriptions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transactions = load_transactions_for_user(db, user.id)
    df = transactions_to_df(transactions)
    recurring = subs.detect_recurring(df)
    return [
        RecurringExpenseOut(
            merchant=r["merchant"], category=r.get("category"), average_amount=r["average_amount"],
            frequency=r["frequency"], monthly_equivalent=subs.monthly_equivalent(r["average_amount"], r["frequency"]),
            confidence_score=r["confidence_score"], first_seen=r["first_seen"], last_seen=r["last_seen"],
            is_active=r["is_active"],
        ) for r in recurring
    ]
