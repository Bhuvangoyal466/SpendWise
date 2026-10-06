
"""
SpendWise LLM Client

This is the ONLY module that communicates with an external LLM.

Current provider:
    Groq

Architecture:
    Backend / analytics / simulation
                ↓
        Structured financial data
                ↓
        This module / Groq
                ↓
        Natural-language explanation

IMPORTANT:
The LLM never calculates financial numbers.
All financial arithmetic is performed by the backend first.
The LLM only converts already-computed data into readable language.
"""

import os
import json
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# GROQ CONFIGURATION
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)


# ============================================================
# GROQ CLIENT
# ============================================================

_client = None

if GROQ_API_KEY:
    try:
        from groq import Groq

        _client = Groq(
            api_key=GROQ_API_KEY
        )

    except ImportError:
        _client = None


# ============================================================
# SYSTEM PROMPTS
# ============================================================

EXPLANATION_SYSTEM_PROMPT = """
You are the SpendWise financial explanation assistant.

You will receive financial findings that have already been calculated
by the SpendWise backend.

Your job is ONLY to explain those findings clearly.

STRICT RULES:

1. Never invent financial numbers.
2. Never perform financial calculations yourself.
3. Only use numbers explicitly present in the supplied data.
4. Do not introduce percentages, totals, averages, or estimates
   that are not present in the supplied data.
5. Do not repeat raw JSON.
6. Do not mention APIs, databases, prompts, models, or implementation.
7. Keep the response concise and natural.
8. Use Indian Rupee notation (₹) when discussing INR amounts.
9. Do not make unsupported claims about why a user spent money.
"""


ASSISTANT_SYSTEM_PROMPT = """
You are the SpendWise AI Financial Assistant.

The user's question has already been classified and answered by
SpendWise's deterministic financial backend.

You are given:
    1. The user's original question.
    2. Financial data calculated by the backend.

Your job is ONLY to explain that data naturally.

STRICT RULES:

1. Never calculate financial values yourself.
2. Never invent numbers.
3. Only use numbers present in the supplied data.
4. Never contradict the supplied data.
5. Do not repeat the raw JSON.
6. Answer the user's actual question directly.
7. Keep the response concise: normally 1-3 sentences.
8. Use Indian Rupee notation (₹) for INR values.
9. If the supplied data says that no information is available,
   clearly tell the user that.
10. Do not mention APIs, databases, prompts, models, or implementation.
"""


# ============================================================
# AVAILABILITY
# ============================================================

def is_llm_available() -> bool:
    """
    Returns True if Groq is configured and available.
    """
    return _client is not None


# ============================================================
# GENERIC GROQ GENERATION
# ============================================================

def _generate(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 300,
    temperature: float = 0.2,
) -> Optional[str]:
    """
    Internal Groq generation function.

    Returns:
        Generated text if successful.
        None if Groq is unavailable or the request fails.
    """

    if _client is None:
        return None

    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if not response.choices:
            return None

        message = response.choices[0].message

        if not message or not message.content:
            return None

        return message.content.strip()

    except Exception as exc:
        print(f"[Groq] Request failed: {exc}")
        return None


# ============================================================
# INSIGHT ENGINE
# ============================================================

def explain_finding(
    structured_finding: dict,
    instruction: str,
) -> str:
    """
    Explain an already-computed financial finding.

    Used by:
        app.ai.insight_engine

    The LLM receives only structured backend data.
    """

    user_content = (
        f"Instruction:\n{instruction}\n\n"
        f"Computed financial finding:\n"
        f"{json.dumps(structured_finding, default=str, ensure_ascii=False)}"
    )

    response = _generate(
        system_prompt=EXPLANATION_SYSTEM_PROMPT,
        user_prompt=user_content,
        max_tokens=250,
        temperature=0.2,
    )

    if response:
        return response

    return _template_fallback(structured_finding)


# ============================================================
# AI ASSISTANT
# ============================================================

def answer_with_data(
    question: str,
    data: dict,
) -> str:
    """
    Convert backend-computed data into a natural-language answer.

    Used by:
        app.ai.assistant

    IMPORTANT:
    This function does NOT calculate anything.
    """

    user_content = (
        f"User question:\n{question}\n\n"
        f"Computed financial data:\n"
        f"{json.dumps(data, default=str, ensure_ascii=False)}"
    )

    response = _generate(
        system_prompt=ASSISTANT_SYSTEM_PROMPT,
        user_prompt=user_content,
        max_tokens=300,
        temperature=0.2,
    )

    if response:
        return response

    return _template_answer_fallback(
        question,
        data,
    )


# ============================================================
# DETERMINISTIC FALLBACK
# ============================================================

def _template_fallback(
    finding: dict,
    error: Optional[str] = None,
) -> str:
    """
    Fallback for Insight Engine when Groq is unavailable.

    This ensures the application remains usable even without
    an external LLM.
    """

    finding_type = (
        finding.get("type")
        or finding.get("category")
    )

    # Spending increase
    if (
        finding_type == "category_increase"
        or finding.get("trend") == "increasing"
    ):
        category = finding.get(
            "category",
            "this category",
        )

        pct = finding.get(
            "pct_change",
            "?",
        )

        return (
            f"Spending on {category} increased "
            f"by {pct}% compared with the previous period."
        )

    # Spending decrease
    if finding.get("trend") == "decreasing":

        category = finding.get(
            "category",
            "this category",
        )

        pct = abs(
            finding.get(
                "pct_change",
                0,
            )
        )

        return (
            f"Spending on {category} decreased "
            f"by {pct}% compared with the previous period."
        )

    # Anomaly
    if "anomaly_score" in finding:

        reason = finding.get(
            "reason",
            {},
        )

        if isinstance(reason, dict):
            message = reason.get(
                "message"
            )

            if message:
                return message

        return "An unusual transaction was detected."

    # Recurring expense
    if finding_type == "recurring_expense":

        merchant = finding.get(
            "merchant",
            "This expense",
        )

        return (
            f"{merchant} appears to be a recurring expense "
            f"based on your transaction history."
        )

    # Behavioral profile
    if finding_type == "behavioral_profile":
        return (
            "Your spending behavior has been analyzed "
            "based on your transaction history."
        )

    # Goal risk
    if finding_type == "goal_risk":
        return (
            "One of your financial goals may require "
            "adjustment based on your current spending pattern."
        )

    return (
        "Here's a summary of this finding based on your data."
    )


# ============================================================
# ASSISTANT FALLBACK
# ============================================================

def _template_answer_fallback(
    question: str,
    data: dict,
) -> str:
    """
    Natural-language fallback when Groq is unavailable.

    This replaces the old behavior that exposed raw JSON
    and mentioned ANTHROPIC_API_KEY.
    """

    if not data:
        return (
            "I couldn't find enough information in your "
            "financial data to answer that question."
        )

    # --------------------------------------------------------
    # Category spending
    # --------------------------------------------------------

    if "category" in data and "total" in data:

        category = data.get(
            "category",
            "this category",
        )

        total = data.get(
            "total",
            0,
        )

        count = data.get(
            "count",
        )

        average = data.get(
            "average",
        )

        pct = data.get(
            "pct_of_total",
        )

        if count is not None and pct is not None:

            return (
                f"You spent ₹{float(total):,.2f} on {category} "
                f"across {int(count)} transactions, which accounts "
                f"for {float(pct):.2f}% of your total spending."
            )

        if count is not None:

            return (
                f"You spent ₹{float(total):,.2f} on {category} "
                f"across {int(count)} transactions."
            )

        return (
            f"You spent ₹{float(total):,.2f} on {category}."
        )

    # --------------------------------------------------------
    # No transactions
    # --------------------------------------------------------

    if data.get("total") == 0:

        category = data.get(
            "category",
            "that category",
        )

        return (
            f"I couldn't find any transactions "
            f"for {category}."
        )

    # --------------------------------------------------------
    # Explicit note
    # --------------------------------------------------------

    if data.get("note"):
        return str(data["note"])

    # --------------------------------------------------------
    # Generic fallback
    # --------------------------------------------------------

    return (
        "I found the relevant financial information, "
        "but I'm unable to generate the full AI explanation "
        "right now."
    )
