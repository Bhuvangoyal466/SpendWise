from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import User
from app.schemas.schemas import DashboardSummary
from app.api.auth import get_current_user
from app.api.deps import load_transactions_for_user
from app.analytics import core as analytics
from app.analytics.core import transactions_to_df

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(start: Optional[date] = None, end: Optional[date] = None,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transactions = load_transactions_for_user(db, user.id)
    df = transactions_to_df(transactions)

    end = end or (df["date"].max().date() if not df.empty else date.today())
    start = start or (end - timedelta(days=90))

    period_df = df[(df["date"] >= str(start)) & (df["date"] <= str(end))] if not df.empty else df
    summary = analytics.summarize(period_df)

    return DashboardSummary(
        period_start=start, period_end=end,
        total_income=summary["total_income"], total_expenses=summary["total_expenses"],
        net_savings=summary["net_savings"], savings_rate=summary["savings_rate"],
        average_transaction=summary["average_transaction"],
        top_categories=analytics.top_categories(period_df),
        top_merchants=analytics.top_merchants(period_df),
        category_breakdown=analytics.category_breakdown(period_df),
        monthly_trend=analytics.monthly_trend(df),  # full history for the trend chart
        weekday_weekend=analytics.weekday_weekend_split(period_df),
        category_concentration=analytics.category_concentration_index(period_df),
    )


@router.get("/heatmap")
def dashboard_heatmap(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transactions = load_transactions_for_user(db, user.id)
    df = transactions_to_df(transactions)
    return {"data": analytics.heatmap_data(df)}
