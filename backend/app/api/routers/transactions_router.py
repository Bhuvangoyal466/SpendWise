import csv
import io
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Transaction, User, TransactionType, Category
from app.schemas.schemas import TransactionCreate, TransactionUpdate, TransactionOut, CSVImportResult
from app.api.auth import get_current_user
from app.api.deps import get_or_create_category
from app.data.synthetic import generate_transactions, SyntheticProfile

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _to_out(t: Transaction, category_name: Optional[str]) -> TransactionOut:
    return TransactionOut(
        id=t.id, date=t.date, amount=t.amount,
        transaction_type=t.transaction_type.value if hasattr(t.transaction_type, "value") else t.transaction_type,
        category=category_name, merchant=t.merchant, description=t.description,
        payment_method=t.payment_method, is_synthetic=t.is_synthetic,
    )


@router.get("", response_model=List[TransactionOut])
def list_transactions(
    start: Optional[date] = None, end: Optional[date] = None,
    category: Optional[str] = None, limit: int = Query(500, le=2000),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    q = db.query(Transaction).filter(Transaction.user_id == user.id)
    if start:
        q = q.filter(Transaction.date >= start)
    if end:
        q = q.filter(Transaction.date <= end)
    rows = q.order_by(Transaction.date.desc()).limit(limit).all()
    cat_map = {c.id: c.name for c in db.query(Category).filter(
        (Category.user_id == user.id) | (Category.user_id.is_(None))
    ).all()}
    results = [_to_out(t, cat_map.get(t.category_id, "Uncategorized")) for t in rows]
    if category:
        results = [r for r in results if r.category == category]
    return results


@router.post("", response_model=TransactionOut)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    cat = get_or_create_category(db, user.id, payload.category_name) if payload.category_name else None
    t = Transaction(
        user_id=user.id, date=payload.date, amount=payload.amount,
        transaction_type=TransactionType(payload.transaction_type),
        category_id=cat.id if cat else None, merchant=payload.merchant,
        description=payload.description, payment_method=payload.payment_method,
        is_synthetic=False,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_out(t, cat.name if cat else None)


@router.put("/{transaction_id}", response_model=TransactionOut)
def update_transaction(transaction_id: str, payload: TransactionUpdate, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    t = db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if payload.date is not None:
        t.date = payload.date
    if payload.amount is not None:
        t.amount = payload.amount
    if payload.amount is not None and payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    if payload.transaction_type is not None:
        try:
            t.transaction_type = TransactionType(payload.transaction_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail="transaction_type must be income or expense")
    if payload.merchant is not None:
        t.merchant = payload.merchant
    if payload.description is not None:
        t.description = payload.description
    if payload.payment_method is not None:
        t.payment_method = payload.payment_method
    cat_name = None
    if payload.category_name is not None:
        cat = get_or_create_category(db, user.id, payload.category_name)
        t.category_id = cat.id
        cat_name = cat.name
    db.commit()
    db.refresh(t)
    return _to_out(t, cat_name)


@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(t)
    db.commit()
    return {"status": "deleted"}


@router.post("/import-csv", response_model=CSVImportResult)
def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    """
    Expects columns (case-insensitive, flexible order): date, amount, type,
    category, merchant, description, payment_method.
    `type` should be 'income' or 'expense'. Amount should be positive.
    """
    content = file.file.read().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    normalized_fields = {f.lower().strip(): f for f in (reader.fieldnames or [])}

    required = ["date", "amount", "type"]
    missing = [r for r in required if r not in normalized_fields]
    if missing:
        raise HTTPException(status_code=400, detail=f"CSV missing required columns: {missing}")

    imported, skipped, errors = 0, 0, []
    seen_keys = set()
    for i, row in enumerate(reader, start=2):
        try:
            raw_date = row[normalized_fields["date"]].strip()
            parsed_date = None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
                try:
                    parsed_date = datetime.strptime(raw_date, fmt).date()
                    break
                except ValueError:
                    continue
            if parsed_date is None:
                raise ValueError(f"unparseable date '{raw_date}'")

            amount = abs(float(row[normalized_fields["amount"]]))
            ttype = row[normalized_fields["type"]].strip().lower()
            if ttype not in ("income", "expense"):
                raise ValueError(f"invalid type '{ttype}'")

            description = row.get(normalized_fields.get("description", ""), "")
            merchant = row.get(normalized_fields.get("merchant", ""), "")

            dedupe_key = (parsed_date, amount, description, merchant)
            if dedupe_key in seen_keys:
                skipped += 1
                continue
            seen_keys.add(dedupe_key)

            category_name = row.get(normalized_fields.get("category", ""), None)
            cat = get_or_create_category(db, user.id, category_name) if category_name else None

            t = Transaction(
                user_id=user.id, date=parsed_date, amount=amount,
                transaction_type=TransactionType(ttype), category_id=cat.id if cat else None,
                merchant=merchant or None, description=description or None,
                payment_method=row.get(normalized_fields.get("payment_method", ""), None),
                is_synthetic=False,
            )
            db.add(t)
            imported += 1
        except Exception as e:
            skipped += 1
            errors.append(f"Row {i}: {e}")

    db.commit()
    return CSVImportResult(rows_received=imported + skipped, rows_imported=imported,
                            rows_skipped=skipped, errors=errors[:20])


@router.post("/seed-synthetic")
def seed_synthetic(months: int = 6, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Generates and persists realistic synthetic transaction history for demo/testing."""
    rows = generate_transactions(months=months, profile=SyntheticProfile())
    created = 0
    for row in rows:
        cat = get_or_create_category(db, user.id, row["category_name"])
        t = Transaction(
            user_id=user.id, date=row["date"], amount=row["amount"],
            transaction_type=TransactionType(row["transaction_type"]), category_id=cat.id,
            merchant=row["merchant"], description=row["description"],
            payment_method=row["payment_method"], is_synthetic=True,
        )
        db.add(t)
        created += 1
    db.commit()
    return {"status": "ok", "transactions_created": created}
