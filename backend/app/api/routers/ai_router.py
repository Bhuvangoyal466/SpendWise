from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import User, Insight, InsightCategory, Goal
from app.schemas.schemas import InsightOut, AssistantQuery, AssistantResponse
from app.api.auth import get_current_user
from app.api.deps import load_transactions_for_user
from app.analytics.core import transactions_to_df
from app.behavioral import scoring as behavioral
from app.ml import anomaly as anomaly_ml
from app.subscriptions import detector as subs
from app.goals.service import evaluate_goal
from app.ai.insight_engine import generate_insights
from app.ai.assistant import handle_question
from app.utils.json_safe import to_jsonable
from datetime import date

router = APIRouter(prefix="/api", tags=["ai"])


@router.post("/insights/generate", response_model=List[InsightOut])
def generate_user_insights(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transactions = load_transactions_for_user(db, user.id)
    df = transactions_to_df(transactions)
    if df.empty:
        return []

    behavioral_scores = behavioral.compute_behavioral_scores(df)
    raw_anomalies = anomaly_ml.detect_anomalies(df)
    anomalies = []
    for r in raw_anomalies[:5]:
        row = df.loc[r["transaction_index"]]
        anomalies.append({**r, "date": str(row["date"].date()), "amount": row["amount"],
                           "category": row.get("category"), "merchant": row.get("merchant")})
    recurring = subs.detect_recurring(df)

    goals = db.query(Goal).filter(Goal.user_id == user.id).all()
    goal_evals = [
        {"name": g.name, **evaluate_goal(g.target_amount, g.current_saved, g.target_date, date.today(), 0)}
        for g in goals
    ]

    generated = generate_insights(df, behavioral_scores, anomalies, recurring, goal_evals)

    saved = []
    for item in generated:
        insight = Insight(
            user_id=user.id, category=InsightCategory(item["category"]),
            structured_finding=to_jsonable(item["structured_finding"]), narrative=item["narrative"],
        )
        db.add(insight)
        saved.append(insight)
    db.commit()
    for s in saved:
        db.refresh(s)

    return [
        InsightOut(id=s.id, category=s.category.value, structured_finding=s.structured_finding,
                   narrative=s.narrative, generated_at=s.generated_at)
        for s in saved
    ]


@router.get("/insights", response_model=List[InsightOut])
def list_insights(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (db.query(Insight).filter(Insight.user_id == user.id, Insight.dismissed == False)
            .order_by(Insight.generated_at.desc()).limit(50).all())
    return [
        InsightOut(id=r.id, category=r.category.value, structured_finding=r.structured_finding,
                   narrative=r.narrative, generated_at=r.generated_at)
        for r in rows
    ]


@router.post("/assistant/ask", response_model=AssistantResponse)
def ask_assistant(payload: AssistantQuery, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transactions = load_transactions_for_user(db, user.id)
    df = transactions_to_df(transactions)

    goals = db.query(Goal).filter(Goal.user_id == user.id).all()
    goal_data = [
        {"name": g.name, **evaluate_goal(g.target_amount, g.current_saved, g.target_date, date.today(), 0)}
        for g in goals
    ]

    result = handle_question(payload.question, df, goal_data)
    return AssistantResponse(**result)
