"""Pydantic schemas — API request/response contracts."""
from datetime import date, datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, EmailStr, Field


# ---------- Auth / Users ----------

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class UserOut(BaseModel):
    id: str
    email: str
    name: Optional[str]
    base_currency: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Categories ----------

class CategoryOut(BaseModel):
    id: str
    name: str
    parent_category: Optional[str]
    icon: Optional[str]
    color: Optional[str]

    class Config:
        from_attributes = True


# ---------- Transactions ----------

class TransactionCreate(BaseModel):
    date: date
    amount: float = Field(gt=0, description="Always positive; sign implied by transaction_type")
    transaction_type: Literal["income", "expense"]
    category_name: Optional[str] = None
    merchant: Optional[str] = None
    description: Optional[str] = None
    payment_method: Optional[str] = None


class TransactionUpdate(BaseModel):
    date: Optional[date] = None
    amount: Optional[float] = Field(default=None, gt=0)
    transaction_type: Optional[Literal["income", "expense"]] = None
    category_name: Optional[str] = None
    merchant: Optional[str] = None
    description: Optional[str] = None
    payment_method: Optional[str] = None


class TransactionOut(BaseModel):
    id: str
    date: date
    amount: float
    transaction_type: str
    category: Optional[str] = None
    merchant: Optional[str]
    description: Optional[str]
    payment_method: Optional[str]
    is_synthetic: bool

    class Config:
        from_attributes = True


class CSVImportResult(BaseModel):
    rows_received: int
    rows_imported: int
    rows_skipped: int
    errors: List[str]


# ---------- Goals ----------

class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_amount: float = Field(gt=0)
    current_saved: float = Field(default=0.0, ge=0)
    target_date: date


class GoalOut(BaseModel):
    id: str
    name: str
    target_amount: float
    current_saved: float
    target_date: date
    remaining_amount: float
    months_left: float
    required_monthly_savings: float
    feasible: Optional[bool]
    feasibility_note: str


# ---------- Dashboard / Analytics ----------

class DashboardSummary(BaseModel):
    period_start: date
    period_end: date
    total_income: float
    total_expenses: float
    net_savings: float
    savings_rate: float
    average_transaction: float
    top_categories: List[Dict[str, Any]]
    top_merchants: List[Dict[str, Any]]
    category_breakdown: List[Dict[str, Any]]
    monthly_trend: List[Dict[str, Any]]
    weekday_weekend: Dict[str, float]
    category_concentration: float


# ---------- Behavioral ----------

class BehavioralScoreOut(BaseModel):
    savings_discipline: float
    expense_stability: float
    spending_consistency: float
    impulse_tendency: float
    weekend_spending_tendency: float
    subscription_burden: float
    category_concentration: float
    goal_readiness: float
    personality_label: str
    explanation: Dict[str, str]


# ---------- Anomalies ----------

class AnomalyOut(BaseModel):
    id: str
    transaction_id: str
    date: date
    amount: float
    merchant: Optional[str]
    category: Optional[str]
    anomaly_score: float
    method: str
    reason: Dict[str, Any]


# ---------- Forecast ----------

class ForecastPoint(BaseModel):
    date: date
    value: float
    lower: float
    upper: float


class ForecastOut(BaseModel):
    method: str
    horizon_days: int
    category: Optional[str]
    points: List[ForecastPoint]
    evaluation: Optional[Dict[str, float]]
    insufficient_data: bool = False


# ---------- Subscriptions ----------

class RecurringExpenseOut(BaseModel):
    merchant: str
    category: Optional[str]
    average_amount: float
    frequency: str
    monthly_equivalent: float
    confidence_score: float
    first_seen: date
    last_seen: date
    is_active: bool


# ---------- Simulation ----------

class ScenarioAssumptions(BaseModel):
    category_pct_changes: Dict[str, float] = Field(
        default_factory=dict,
        description="e.g. {'Shopping': -0.3} = reduce Shopping spend by 30%",
    )
    income_pct_change: float = 0.0
    disable_recurring_merchants: List[str] = Field(default_factory=list)
    savings_target_override: Optional[float] = None


class SimulationRequest(BaseModel):
    mode: str = "forward"  # "forward" | "time_machine"
    assumptions: ScenarioAssumptions
    horizon_months: int = 6
    # time_machine only:
    period_start: Optional[date] = None
    period_end: Optional[date] = None


class SimulationResult(BaseModel):
    id: str
    mode: str
    baseline: Dict[str, Any]
    simulated: Dict[str, Any]
    delta: Dict[str, Any]
    trajectory: List[Dict[str, Any]]
    assumptions_used: Dict[str, Any]
    goal_impact: Optional[Dict[str, Any]] = None
    disclaimer: str


# ---------- Insights ----------

class InsightOut(BaseModel):
    id: str
    category: str
    structured_finding: Dict[str, Any]
    narrative: Optional[str]
    generated_at: datetime


# ---------- AI Assistant ----------

class AssistantQuery(BaseModel):
    question: str


class AssistantResponse(BaseModel):
    answer: str
    intent: str
    data_used: Dict[str, Any]
