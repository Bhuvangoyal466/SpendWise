"""Shared query helpers used across multiple API routers."""
from typing import List
from sqlalchemy.orm import Session

from app.models.models import Transaction, Category
from app.analytics.core import transactions_to_df


def load_transactions_for_user(db: Session, user_id: str):
    rows = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .all()
    )
    cat_map = {c.id: c.name for c in db.query(Category).filter(
        (Category.user_id == user_id) | (Category.user_id.is_(None))
    ).all()}

    dicts = []
    for t in rows:
        dicts.append({
            "id": t.id,
            "date": t.date,
            "amount": t.amount,
            "transaction_type": t.transaction_type.value if hasattr(t.transaction_type, "value") else t.transaction_type,
            "category": cat_map.get(t.category_id, "Uncategorized"),
            "merchant": t.merchant,
            "description": t.description,
            "payment_method": t.payment_method,
            "is_synthetic": t.is_synthetic,
        })
    return dicts


def get_or_create_category(db: Session, user_id: str, name: str) -> Category:
    existing = db.query(Category).filter(
        Category.name == name,
        ((Category.user_id == user_id) | (Category.user_id.is_(None)))
    ).first()
    if existing:
        return existing
    cat = Category(user_id=user_id, name=name)
    db.add(cat)
    db.flush()
    return cat
