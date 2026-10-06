"""
SQLAlchemy models — one table per entity in the project plan's data model
(section 3 / 20 of the brief).

Design rule enforced here: `insights`, `behavioral_scores`, `anomalies`,
`forecasts`, and `simulations` all store their *structured numeric finding*
in a JSON column separate from any LLM-generated narrative text, so the
number on screen is never something the LLM invented — see ai/insight_engine.py.
"""
import enum
import uuid
from datetime import datetime, date as date_type

from sqlalchemy import (
    Column, String, Float, Boolean, DateTime, Date, ForeignKey, Integer,
    Enum, JSON, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"


class SimulationMode(str, enum.Enum):
    forward = "forward"
    time_machine = "time_machine"


class InsightCategory(str, enum.Enum):
    spending_change = "spending_change"
    anomaly = "anomaly"
    goal_risk = "goal_risk"
    subscription = "subscription"
    behavioral = "behavioral"
    forecast = "forecast"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    base_currency = Column(String, default="USD")
    created_at = Column(DateTime, default=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # null = system default category
    name = Column(String, nullable=False)
    parent_category = Column(String, nullable=True)
    icon = Column(String, nullable=True)
    color = Column(String, nullable=True)

    user = relationship("User", back_populates="categories")

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_category_name"),)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Float, nullable=False)  # always positive; sign implied by transaction_type
    transaction_type = Column(Enum(TransactionType), nullable=False)
    category_id = Column(String, ForeignKey("categories.id"), nullable=True)
    merchant = Column(String, nullable=True, index=True)
    description = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)
    is_synthetic = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")
    category = relationship("Category")


class RecurringExpense(Base):
    __tablename__ = "recurring_expenses"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    merchant = Column(String, nullable=False)
    category_id = Column(String, ForeignKey("categories.id"), nullable=True)
    average_amount = Column(Float, nullable=False)
    frequency = Column(String, nullable=False)  # weekly / monthly / annual
    first_seen = Column(Date, nullable=False)
    last_seen = Column(Date, nullable=False)
    confidence_score = Column(Float, nullable=False)  # 0-1
    is_active = Column(Boolean, default=True)


class Goal(Base):
    __tablename__ = "goals"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    current_saved = Column(Float, default=0.0)
    target_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="goals")


class BehavioralScore(Base):
    __tablename__ = "behavioral_scores"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    computed_at = Column(DateTime, default=datetime.utcnow)
    savings_discipline = Column(Float)
    expense_stability = Column(Float)
    spending_consistency = Column(Float)
    impulse_tendency = Column(Float)
    weekend_spending_tendency = Column(Float)
    subscription_burden = Column(Float)
    category_concentration = Column(Float)
    goal_readiness = Column(Float)
    personality_label = Column(String, nullable=True)


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    anomaly_score = Column(Float, nullable=False)
    method = Column(String, nullable=False)  # isolation_forest / statistical
    reason = Column(JSON, nullable=False)  # structured explanation, e.g. {"feature": "amount_zscore", "value": 4.2}
    reviewed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    category_id = Column(String, ForeignKey("categories.id"), nullable=True)  # null = total spend
    horizon_days = Column(Integer, nullable=False)
    method = Column(String, nullable=False)
    predicted_values = Column(JSON, nullable=False)  # [{date, value, lower, upper}, ...]
    evaluation = Column(JSON, nullable=True)  # {"mae": ..., "mape": ...} from backtest


class Simulation(Base):
    __tablename__ = "simulations"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    mode = Column(Enum(SimulationMode), nullable=False)
    baseline_snapshot = Column(JSON, nullable=False)
    assumptions = Column(JSON, nullable=False)
    results = Column(JSON, nullable=False)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)


class Insight(Base):
    __tablename__ = "insights"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    category = Column(Enum(InsightCategory), nullable=False)
    structured_finding = Column(JSON, nullable=False)  # the deterministic fact
    narrative = Column(Text, nullable=True)             # the LLM's explanation of that fact
    dismissed = Column(Boolean, default=False)
