"""
SpendWise AI Financial Assistant

The assistant is a controlled financial chatbot.

Architecture:
    User Question
        ↓
    Intent Classification
        ↓
    Deterministic Backend Calculation
        ↓
    Structured Financial Data
        ↓
    Groq LLM for Natural-Language Explanation
        ↓
    User Response

IMPORTANT:
- The LLM does NOT calculate financial numbers.
- Financial calculations are performed using the user's transaction data.
- The LLM only explains already-computed results.
"""

import re
from typing import Dict, Any, Optional, List

import pandas as pd

from app.analytics import core as analytics
from app.simulation import engine as simulation
from app.ai.client import answer_with_data


# ---------------------------------------------------------------------------
# SUPPORTED CATEGORIES
# ---------------------------------------------------------------------------

CATEGORY_WORDS = [
    "groceries",
    "grocery",
    "dining",
    "food",
    "transport",
    "transportation",
    "shopping",
    "entertainment",
    "utilities",
    "utility",
    "health",
    "healthcare",
    "housing",
    "education",
    "travel",
    "subscriptions",
    "subscription",
]


# ---------------------------------------------------------------------------
# CATEGORY HELPERS
# ---------------------------------------------------------------------------

def _find_category(question: str) -> Optional[str]:
    """
    Detect a spending category from the user's question.
    """

    q = question.lower()

    aliases = {
        "grocery": "Groceries",
        "groceries": "Groceries",
        "food": "Dining",
        "dining": "Dining",
        "transport": "Transport",
        "transportation": "Transport",
        "shopping": "Shopping",
        "entertainment": "Entertainment",
        "utilities": "Utilities",
        "utility": "Utilities",
        "health": "Health",
        "healthcare": "Health",
        "housing": "Housing",
        "education": "Education",
        "travel": "Travel",
        "subscription": "Subscriptions",
        "subscriptions": "Subscriptions",
    }

    for word, category in aliases.items():
        if re.search(rf"\b{re.escape(word)}\b", q):
            return category

    return None


def _find_pct(question: str) -> float:
    """
    Extract percentage from a what-if question.

    Example:
        "reduce shopping by 20%" -> 0.20

    Defaults to 20%.
    """

    match = re.search(r"(\d+(?:\.\d+)?)\s*%", question)

    if match:
        return float(match.group(1)) / 100

    return 0.20


# ---------------------------------------------------------------------------
# DATA NORMALIZATION HELPERS
# ---------------------------------------------------------------------------

def _find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """
    Find a dataframe column without depending on exact capitalization.
    """

    if df is None or df.empty:
        return None

    normalized = {
        str(col).strip().lower().replace(" ", "_"): col
        for col in df.columns
    }

    for candidate in candidates:
        key = candidate.lower().replace(" ", "_")

        if key in normalized:
            return normalized[key]

    return None


def _get_amount_column(df: pd.DataFrame) -> Optional[str]:
    return _find_column(
        df,
        [
            "amount",
            "transaction_amount",
            "value",
            "price",
        ],
    )


def _get_type_column(df: pd.DataFrame) -> Optional[str]:
    return _find_column(
        df,
        [
            "transaction_type",
            "type",
            "transactiontype",
        ],
    )


def _get_date_column(df: pd.DataFrame) -> Optional[str]:
    return _find_column(
        df,
        [
            "date",
            "transaction_date",
            "timestamp",
            "datetime",
        ],
    )


def _calculate_financial_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate total income, expenses and savings directly from transactions.

    This function is deliberately deterministic.
    """

    if df is None or df.empty:
        return {
            "total_income": 0.0,
            "total_expenses": 0.0,
            "total_savings": 0.0,
            "savings_rate": 0.0,
            "transaction_count": 0,
        }

    amount_col = _get_amount_column(df)
    type_col = _get_type_column(df)

    if not amount_col:
        return {
            "total_income": 0.0,
            "total_expenses": 0.0,
            "total_savings": 0.0,
            "savings_rate": 0.0,
            "transaction_count": len(df),
            "note": "Unable to identify the transaction amount column.",
        }

    work = df.copy()

    work[amount_col] = pd.to_numeric(
        work[amount_col],
        errors="coerce"
    ).fillna(0)

    # ---------------------------------------------------------------
    # Preferred method: transaction_type
    # ---------------------------------------------------------------

    if type_col:

        transaction_types = (
            work[type_col]
            .astype(str)
            .str.lower()
            .str.strip()
        )

        income_mask = transaction_types.isin(
            [
                "income",
                "credit",
                "salary",
                "deposit",
                "earning",
                "earnings",
            ]
        )

        expense_mask = transaction_types.isin(
            [
                "expense",
                "debit",
                "spending",
                "purchase",
                "payment",
            ]
        )

        total_income = float(
            work.loc[income_mask, amount_col].abs().sum()
        )

        total_expenses = float(
            work.loc[expense_mask, amount_col].abs().sum()
        )

        # If the type column exists but uses unexpected values,
        # fall back to signed amounts.
        if total_income == 0 and total_expenses == 0:

            positive = work[amount_col] > 0
            negative = work[amount_col] < 0

            total_income = float(
                work.loc[positive, amount_col].sum()
            )

            total_expenses = float(
                work.loc[negative, amount_col].abs().sum()
            )

    else:
        # -----------------------------------------------------------
        # Fallback: infer income/expense from amount sign
        # -----------------------------------------------------------

        positive = work[amount_col] > 0
        negative = work[amount_col] < 0

        total_income = float(
            work.loc[positive, amount_col].sum()
        )

        total_expenses = float(
            work.loc[negative, amount_col].abs().sum()
        )

    savings = total_income - total_expenses

    savings_rate = (
        (savings / total_income) * 100
        if total_income > 0
        else 0.0
    )

    return {
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "total_savings": round(savings, 2),
        "savings_rate": round(savings_rate, 2),
        "transaction_count": int(len(work)),
    }


# ---------------------------------------------------------------------------
# SAVINGS TREND
# ---------------------------------------------------------------------------

def _calculate_savings_trend(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate monthly income, expenses and savings.

    Returns a deterministic trend that the LLM can explain.
    """

    if df is None or df.empty:
        return {
            "available": False,
            "trend": "unavailable",
            "message": "There is not enough transaction data to calculate a savings trend.",
        }

    amount_col = _get_amount_column(df)
    type_col = _get_type_column(df)
    date_col = _get_date_column(df)

    if not amount_col or not date_col:
        return {
            "available": False,
            "trend": "unavailable",
            "message": "Transaction dates or amounts are unavailable.",
        }

    work = df.copy()

    work[date_col] = pd.to_datetime(
        work[date_col],
        errors="coerce"
    )

    work[amount_col] = pd.to_numeric(
        work[amount_col],
        errors="coerce"
    ).fillna(0)

    work = work.dropna(subset=[date_col])

    if work.empty:
        return {
            "available": False,
            "trend": "unavailable",
            "message": "There is not enough dated transaction data to calculate a savings trend.",
        }

    work["_month"] = work[date_col].dt.to_period("M")

    monthly_rows = []

    for month, group in work.groupby("_month"):

        if type_col:

            types = (
                group[type_col]
                .astype(str)
                .str.lower()
                .str.strip()
            )

            income_mask = types.isin(
                [
                    "income",
                    "credit",
                    "salary",
                    "deposit",
                    "earning",
                    "earnings",
                ]
            )

            expense_mask = types.isin(
                [
                    "expense",
                    "debit",
                    "spending",
                    "purchase",
                    "payment",
                ]
            )

            income = float(
                group.loc[income_mask, amount_col].abs().sum()
            )

            expenses = float(
                group.loc[expense_mask, amount_col].abs().sum()
            )

            # Fallback if transaction type values are not recognized.
            if income == 0 and expenses == 0:

                positive = group[amount_col] > 0
                negative = group[amount_col] < 0

                income = float(
                    group.loc[positive, amount_col].sum()
                )

                expenses = float(
                    group.loc[negative, amount_col].abs().sum()
                )

        else:

            positive = group[amount_col] > 0
            negative = group[amount_col] < 0

            income = float(
                group.loc[positive, amount_col].sum()
            )

            expenses = float(
                group.loc[negative, amount_col].abs().sum()
            )

        monthly_rows.append(
            {
                "month": str(month),
                "income": round(income, 2),
                "expenses": round(expenses, 2),
                "savings": round(income - expenses, 2),
            }
        )

    if not monthly_rows:
        return {
            "available": False,
            "trend": "unavailable",
            "message": "Unable to calculate monthly savings.",
        }

    monthly_rows.sort(key=lambda x: x["month"])

    savings_values = [
        row["savings"]
        for row in monthly_rows
    ]

    latest = monthly_rows[-1]

    if len(savings_values) >= 2:

        previous = monthly_rows[-2]

        change = latest["savings"] - previous["savings"]

        if change > 0:
            direction = "improving"
        elif change < 0:
            direction = "declining"
        else:
            direction = "stable"

        pct_change = (
            (change / abs(previous["savings"])) * 100
            if previous["savings"] != 0
            else 0
        )

    else:

        previous = None
        change = 0
        pct_change = 0
        direction = "stable"

    average_monthly_savings = sum(savings_values) / len(savings_values)

    return {
        "available": True,
        "trend": direction,
        "latest_month": latest["month"],
        "latest_month_savings": latest["savings"],
        "previous_month_savings": (
            previous["savings"]
            if previous
            else None
        ),
        "change_from_previous_month": round(change, 2),
        "percentage_change": round(pct_change, 2),
        "average_monthly_savings": round(
            average_monthly_savings,
            2
        ),
        "months_analyzed": len(monthly_rows),
        "monthly_savings": monthly_rows,
    }


# ---------------------------------------------------------------------------
# INTENT CLASSIFICATION
# ---------------------------------------------------------------------------

def classify_intent(question: str) -> str:
    """
    Convert a natural-language question into a controlled backend intent.

    This is intentionally rule-based so the LLM cannot decide what financial
    operation should be performed.
    """

    q = question.lower().strip()

    # ---------------------------------------------------------------
    # WHAT-IF / SIMULATION
    # ---------------------------------------------------------------

    if any(
        phrase in q
        for phrase in [
            "what if",
            "simulate",
            "scenario",
            "if i reduce",
            "if i cut",
            "if i spend less",
            "if i save",
        ]
    ):
        return "simulate"

    # ---------------------------------------------------------------
    # GOALS
    # ---------------------------------------------------------------

    if any(
        phrase in q
        for phrase in [
            "goal",
            "afford",
            "can i buy",
            "can i afford",
            "target",
            "financial goal",
        ]
    ):
        return "goal_status"

    # ---------------------------------------------------------------
    # SAVINGS TREND
    # Check this BEFORE generic savings.
    # ---------------------------------------------------------------

    if (
        "savings trend" in q
        or "saving trend" in q
        or "savings going" in q
        or "saving going" in q
        or "am i saving more" in q
        or "am i saving less" in q
        or "saving pattern" in q
        or "savings pattern" in q
    ):
        return "savings_trend"

    # ---------------------------------------------------------------
    # SAVINGS
    # ---------------------------------------------------------------

    if (
        "savings" in q
        or "saving" in q
        or "saved" in q
    ):
        return "savings"

    # ---------------------------------------------------------------
    # INCOME
    # ---------------------------------------------------------------

    if any(
        phrase in q
        for phrase in [
            "income",
            "earned",
            "earnings",
            "salary",
            "money received",
            "money i received",
        ]
    ):
        return "income"

    # ---------------------------------------------------------------
    # EXPENSES
    # ---------------------------------------------------------------

    if any(
        phrase in q
        for phrase in [
            "expenses",
            "expense",
            "expenditure",
            "how much did i spend",
            "how much have i spent",
            "total spending",
            "total expenditure",
            "total expense",
        ]
    ):
        return "expenses"

    # ---------------------------------------------------------------
    # TOP / HIGHEST SPENDING
    # ---------------------------------------------------------------

    if (
        ("highest" in q or "largest" in q or "most" in q or "top" in q)
        and ("spend" in q or "expense" in q or "category" in q)
    ):
        return "top_category"

    # ---------------------------------------------------------------
    # SPENDING TREND
    # ---------------------------------------------------------------

    if (
        "trend" in q
        or "increasing" in q
        or "decreasing" in q
        or "increased" in q
        or "decreased" in q
        or "changed" in q
        or "change in spending" in q
        or "why did spending" in q
    ):
        return "spending_trend"

    # ---------------------------------------------------------------
    # CATEGORY SPENDING
    # ---------------------------------------------------------------

    category = _find_category(q)

    if category and (
        "spend" in q
        or "spent" in q
        or "expense" in q
        or "cost" in q
        or "money" in q
    ):
        return "category_total"

    # ---------------------------------------------------------------
    # GENERIC SPENDING QUESTIONS
    # ---------------------------------------------------------------

    if (
        "how much" in q
        or "spend" in q
        or "spent" in q
    ):
        return "category_total"

    return "unknown"


# ---------------------------------------------------------------------------
# QUESTION HANDLER
# ---------------------------------------------------------------------------

def handle_question(
    question: str,
    df: pd.DataFrame,
    goals: list
) -> Dict[str, Any]:

    intent = classify_intent(question)
    category = _find_category(question)

    # ===============================================================
    # 1. CATEGORY SPENDING
    # ===============================================================

    if intent == "category_total":

        breakdown = {
            row["category"]: row
            for row in analytics.category_breakdown(df)
        }

        if category and category in breakdown:

            data = {
                "category": category,
                **breakdown[category],
            }

        elif category:

            data = {
                "category": category,
                "total": 0,
                "note": "No transactions found in this category.",
            }

        else:

            data = analytics.summarize(df)

        answer = answer_with_data(
            question,
            data
        )

        return {
            "answer": answer,
            "intent": intent,
            "data_used": data,
        }

    # ===============================================================
    # 2. TOTAL EXPENSES
    # ===============================================================

    if intent == "expenses":

        financials = _calculate_financial_summary(df)

        data = {
            "total_expenses": financials["total_expenses"],
            "total_income": financials["total_income"],
            "total_savings": financials["total_savings"],
            "transaction_count": financials["transaction_count"],
        }

        answer = answer_with_data(
            question,
            data
        )

        return {
            "answer": answer,
            "intent": intent,
            "data_used": data,
        }

    # ===============================================================
    # 3. TOTAL INCOME
    # ===============================================================

    if intent == "income":

        financials = _calculate_financial_summary(df)

        data = {
            "total_income": financials["total_income"],
            "total_expenses": financials["total_expenses"],
            "total_savings": financials["total_savings"],
        }

        answer = answer_with_data(
            question,
            data
        )

        return {
            "answer": answer,
            "intent": intent,
            "data_used": data,
        }

    # ===============================================================
    # 4. CURRENT SAVINGS
    # ===============================================================

    if intent == "savings":

        financials = _calculate_financial_summary(df)

        data = {
            "total_income": financials["total_income"],
            "total_expenses": financials["total_expenses"],
            "current_savings": financials["total_savings"],
            "savings_rate": financials["savings_rate"],
        }

        answer = answer_with_data(
            question,
            data
        )

        return {
            "answer": answer,
            "intent": intent,
            "data_used": data,
        }

    # ===============================================================
    # 5. SAVINGS TREND
    # ===============================================================

    if intent == "savings_trend":

        data = _calculate_savings_trend(df)

        answer = answer_with_data(
            question,
            data
        )

        return {
            "answer": answer,
            "intent": intent,
            "data_used": data,
        }

    # ===============================================================
    # 6. TOP SPENDING CATEGORY
    # ===============================================================

    if intent == "top_category":

        top = analytics.top_categories(
            df,
            n=5
        )

        data = {
            "top_categories": top
        }

        answer = answer_with_data(
            question,
            data
        )

        return {
            "answer": answer,
            "intent": intent,
            "data_used": data,
        }

    # ===============================================================
    # 7. SPENDING TREND
    # ===============================================================

    if intent == "spending_trend":

        finding = analytics.period_over_period_change(
            df,
            category=category
        )

        answer = answer_with_data(
            question,
            finding
        )

        return {
            "answer": answer,
            "intent": intent,
            "data_used": finding,
        }

    # ===============================================================
    # 8. GOAL STATUS
    # ===============================================================

    if intent == "goal_status":

        if not goals:

            data = {
                "note": "No financial goals have been set yet."
            }

        else:

            # Keep existing MVP behaviour:
            # use the first goal unless the frontend later supports
            # goal selection.
            data = goals[0]

        answer = answer_with_data(
            question,
            data
        )

        return {
            "answer": answer,
            "intent": intent,
            "data_used": data,
        }

    # ===============================================================
    # 9. WHAT-IF SIMULATION
    # ===============================================================

    if intent == "simulate":

        pct = _find_pct(question)

        assumptions = {
            "category_pct_changes": {},
            "income_pct_change": 0.0,
        }

        if category:

            assumptions["category_pct_changes"] = {
                category: -pct
            }

        else:

            # Generic:
            # "What if I spend 20% less?"
            #
            # Use the user's highest spending category as the
            # deterministic default.

            top = analytics.top_categories(
                df,
                n=1
            )

            if top:

                assumptions["category_pct_changes"] = {
                    top[0]["category"]: -pct
                }

        result = simulation.run_forward_simulation(
            df,
            assumptions,
            horizon_months=6
        )

        answer = answer_with_data(
            question,
            result
        )

        return {
            "answer": answer,
            "intent": intent,
            "data_used": result,
        }

    # ===============================================================
    # 10. UNKNOWN
    # ===============================================================

    return {
        "answer": (
            "I can help you with your finances. You can ask me things like:\n\n"
            "• How much did I spend on Dining?\n"
            "• What are my current savings?\n"
            "• What is my savings trend?\n"
            "• How much income did I receive?\n"
            "• What are my total expenses?\n"
            "• Which category do I spend the most on?\n"
            "• Why did my spending increase?\n"
            "• Can I afford my goal?\n"
            "• What if I reduce Shopping by 20%?\n\n"
            "Try asking me one of these in your own words."
        ),
        "intent": "unknown",
        "data_used": {},
    }