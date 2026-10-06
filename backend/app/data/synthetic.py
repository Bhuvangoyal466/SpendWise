from pathlib import Path
from dataclasses import dataclass
import pandas as pd


@dataclass
class SyntheticProfile:
    """
    Compatibility class used by the existing transactions router.
    The actual sample data is now loaded from the fixed CSV file.
    """

    name: str = "Hyderabad Software Engineer"
    monthly_income: float = 115000.0
    city: str = "Hyderabad"
    currency: str = "INR"


CSV_PATH = Path(__file__).parent / "SpendWise_Indian_Hyderabad_Sample.csv"


def generate_transactions(
    months: int = 3,
    profile: SyntheticProfile | None = None,
):
    """
    Load the default SpendWise sample dataset.

    IMPORTANT:
    The existing transactions_router expects a list of dictionaries,
    not a Pandas DataFrame.

    Therefore, the CSV is converted into the exact dictionary structure
    expected by the existing seed endpoint.
    """

    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Default SpendWise sample dataset not found at: {CSV_PATH}"
        )

    df = pd.read_csv(CSV_PATH)

    # Normalize column names
    df.columns = [
        str(column).strip().lower()
        for column in df.columns
    ]

    # Make sure required columns exist
    required_columns = [
        "date",
        "amount",
        "type",
        "category",
        "merchant",
        "description",
        "payment_method",
    ]

    for column in required_columns:
        if column not in df.columns:
            df[column] = None

    # Keep only the columns used by SpendWise
    df = df[required_columns].copy()

    # Normalize data types
    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df["amount"] = pd.to_numeric(
        df["amount"],
        errors="coerce"
    )

    df["type"] = (
        df["type"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # Remove invalid rows
    df = df.dropna(
        subset=["date", "amount", "type"]
    )

    # Convert each CSV row into the structure expected
    # by transactions_router.py
    transactions = []

    for _, row in df.iterrows():

        transaction = {
            "date": row["date"].date(),
            "amount": float(row["amount"]),
            "type": row["type"],
            "category_name": (
                None
                if pd.isna(row["category"])
                else str(row["category"]).strip()
            ),
            "merchant": (
                None
                if pd.isna(row["merchant"])
                else str(row["merchant"]).strip()
            ),
            "description": (
                None
                if pd.isna(row["description"])
                else str(row["description"]).strip()
            ),
            "payment_method": (
                None
                if pd.isna(row["payment_method"])
                else str(row["payment_method"]).strip()
            ),
        }

        transactions.append(transaction)

    return transactions