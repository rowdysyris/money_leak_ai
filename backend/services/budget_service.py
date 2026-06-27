"""Budget management and budget status calculations for MoneyLeak AI."""

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import Transaction, UserBudget
from models.enums import TransactionType
from services.analytics_utils import debit_amount, estimate_income, get_category, is_high_value_or_anomaly, parse_date, total_credit_received

BUDGET_FIELD_TO_CATEGORY: dict[str, str] = {
    "food_budget": "Food & Dining",
    "shopping_budget": "Shopping",
    "subscriptions_budget": "Subscriptions",
    "travel_budget": "Travel & Transport",
    "bills_budget": "Bills & Utilities",
}

CATEGORY_TO_BUDGET_FIELD: dict[str, str] = {category: field for field, category in BUDGET_FIELD_TO_CATEGORY.items()}
logger = logging.getLogger("moneyleak-ai.budget")

BUDGET_FIELDS: tuple[str, ...] = (
    "total_monthly_limit",
    "savings_target",
    "food_budget",
    "shopping_budget",
    "subscriptions_budget",
    "travel_budget",
    "bills_budget",
    "custom_budgets",
)


def decimal_or_none(value: Any) -> Decimal | None:
    """Convert a user-provided numeric value to Decimal, preserving None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Budget values must be valid numbers.") from exc


def decimal_to_float(value: Any) -> float | None:
    """Convert Decimal-like values to JSON-safe floats."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError, InvalidOperation):
        return None


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def current_month_bounds(today: date | None = None) -> tuple[date, date]:
    """Return inclusive start and end dates for the month containing today."""
    reference_date = today or date.today()
    start = date(reference_date.year, reference_date.month, 1)
    end = date(reference_date.year, reference_date.month, monthrange(reference_date.year, reference_date.month)[1])
    return start, end


def serialize_budget(budget: UserBudget | None) -> dict[str, Any] | None:
    """Serialize a UserBudget ORM object to an API-safe dictionary."""
    if budget is None:
        return None
    return {
        "id": str(budget.id),
        "user_id": str(budget.user_id),
        "total_monthly_limit": decimal_to_float(budget.total_monthly_limit),
        "savings_target": decimal_to_float(budget.savings_target),
        "food_budget": decimal_to_float(budget.food_budget),
        "shopping_budget": decimal_to_float(budget.shopping_budget),
        "subscriptions_budget": decimal_to_float(budget.subscriptions_budget),
        "travel_budget": decimal_to_float(budget.travel_budget),
        "bills_budget": decimal_to_float(budget.bills_budget),
        "custom_budgets": budget.custom_budgets or {},
        "created_at": budget.created_at.isoformat() if budget.created_at else None,
        "updated_at": budget.updated_at.isoformat() if budget.updated_at else None,
    }


def clean_custom_budgets(custom_budgets: dict[str, Any] | None) -> dict[str, float] | None:
    """Return custom budgets as a clean category-to-amount dictionary."""
    if custom_budgets is None:
        return None
    cleaned: dict[str, float] = {}
    for category, value in custom_budgets.items():
        category_name = str(category).strip()
        amount = decimal_or_none(value)
        if not category_name or amount is None:
            continue
        if amount < 0:
            raise ValueError("Custom budget values cannot be negative.")
        cleaned[category_name] = float(amount)
    return cleaned


def validate_budget_payload(payload: dict[str, Any], partial: bool = False) -> dict[str, Any]:
    """Validate and normalize budget input fields for create or update operations."""
    normalized: dict[str, Any] = {}
    for field in BUDGET_FIELDS:
        if field not in payload:
            continue
        value = payload.get(field)
        if field == "custom_budgets":
            normalized[field] = clean_custom_budgets(value)
            continue
        amount = decimal_or_none(value)
        if amount is not None and amount < 0:
            raise ValueError(f"{field} cannot be negative.")
        normalized[field] = amount
    if not partial:
        for field in BUDGET_FIELDS:
            normalized.setdefault(field, None)
    return normalized


def get_or_create_budget(db: Session, user_id: UUID) -> UserBudget:
    """Return the user's budget record, creating one when missing."""
    budget = db.query(UserBudget).filter(UserBudget.user_id == user_id).first()
    if budget is not None:
        return budget
    now = utc_now()
    budget = UserBudget(user_id=user_id, created_at=now, updated_at=now)
    db.add(budget)
    db.flush()
    return budget


def upsert_budget(db: Session, user_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
    """Create or replace the authenticated user's budget settings."""
    try:
        normalized = validate_budget_payload(payload, partial=True)
        budget = get_or_create_budget(db, user_id)
        for field, value in normalized.items():
            setattr(budget, field, value)
        budget.updated_at = utc_now()
        db.commit()
        db.refresh(budget)
        return {"data": {"budget": serialize_budget(budget)}, "warnings": []}
    except ValueError as exc:
        db.rollback()
        return {"data": None, "warnings": [], "error": {"code": "INVALID_BUDGET", "message": str(exc), "details": {}}}
    except SQLAlchemyError as exc:
        db.rollback()
        return {"data": None, "warnings": [], "error": {"code": "DATABASE_ERROR", "message": "Database operation failed.", "details": {"error_type": exc.__class__.__name__}}}


def update_budget(db: Session, user_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
    """Partially update the authenticated user's budget settings."""
    try:
        normalized = validate_budget_payload(payload, partial=True)
        budget = get_or_create_budget(db, user_id)
        for field, value in normalized.items():
            setattr(budget, field, value)
        budget.updated_at = utc_now()
        db.commit()
        db.refresh(budget)
        warnings: list[str] = []
        if not normalized:
            warnings.append("No budget fields were provided for update.")
        return {"data": {"budget": serialize_budget(budget)}, "warnings": warnings}
    except ValueError as exc:
        db.rollback()
        return {"data": None, "warnings": [], "error": {"code": "INVALID_BUDGET", "message": str(exc), "details": {}}}
    except SQLAlchemyError as exc:
        db.rollback()
        return {"data": None, "warnings": [], "error": {"code": "DATABASE_ERROR", "message": "Database operation failed.", "details": {"error_type": exc.__class__.__name__}}}


def transaction_amount_abs(transaction: Transaction) -> Decimal:
    """Return the absolute transaction amount as Decimal without raising on malformed values."""
    amount = getattr(transaction, "amount", Decimal("0"))
    try:
        return abs(Decimal(str(amount or 0)))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def is_debit_transaction(transaction: Transaction) -> bool:
    """Return True when a transaction represents debit spending."""
    transaction_type = getattr(transaction, "transaction_type", None)
    value = getattr(transaction_type, "value", transaction_type)
    return str(value).lower() == TransactionType.DEBIT.value


def is_credit_transaction(transaction: Transaction) -> bool:
    """Return True when a transaction represents incoming credit."""
    transaction_type = getattr(transaction, "transaction_type", None)
    value = getattr(transaction_type, "value", transaction_type)
    return str(value).lower() == TransactionType.CREDIT.value


def month_bounds_from_key(month_key: str | None, fallback_date: date | None = None) -> tuple[date, date]:
    """Return inclusive month bounds from YYYY-MM input or a fallback date."""
    if month_key:
        try:
            year_text, month_text = month_key.split("-", 1)
            year = int(year_text)
            month = int(month_text)
            if 1 <= month <= 12:
                return date(year, month, 1), date(year, month, monthrange(year, month)[1])
        except (ValueError, AttributeError):
            logger.warning("Invalid budget month key received; falling back to current month", extra={"month_key": month_key})
    return current_month_bounds(fallback_date)


def latest_transaction_month(db: Session, user_id: UUID) -> date | None:
    """Return the first day of the latest uploaded transaction month."""
    try:
        latest = db.query(Transaction.transaction_date).filter(Transaction.user_id == user_id).order_by(Transaction.transaction_date.desc()).first()
    except AttributeError:
        return None
    if latest is None:
        return None
    try:
        latest_date = latest[0]
    except (KeyError, IndexError, TypeError):
        latest_date = latest
    if latest_date is None:
        return None
    return date(latest_date.year, latest_date.month, 1)


def available_transaction_months(db: Session, user_id: UUID) -> list[str]:
    """Return sorted YYYY-MM month keys for the authenticated user."""
    try:
        rows = db.query(Transaction.transaction_date).filter(Transaction.user_id == user_id).all()
    except AttributeError:
        return []
    months = set()
    for row in rows:
        try:
            date_value = row[0]
        except (KeyError, IndexError, TypeError):
            date_value = row
        if date_value is not None:
            months.add(date_value.strftime("%Y-%m"))
    return sorted(months, reverse=True)


def get_month_transactions(db: Session, user_id: UUID, month_key: str | None = None) -> tuple[list[Transaction], str]:
    """Fetch transactions for a selected month, defaulting to the latest transaction month."""
    latest_month = latest_transaction_month(db, user_id)
    month_start, month_end = month_bounds_from_key(month_key, latest_month or date.today())
    try:
        transactions = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= month_start,
                Transaction.transaction_date <= month_end,
            )
            .all()
        )
    except AttributeError:
        transactions = []
    return transactions, month_start.strftime("%Y-%m")


def build_budget_status(category: str, limit: Decimal | None, spent: Decimal) -> dict[str, Any]:
    """Build one category budget status item with safe percentage calculations."""
    if limit is None or limit <= 0:
        return {
            "category": category,
            "spent": float(spent),
            "limit": None,
            "remaining": None,
            "percentage_used": 0.0,
            "status": "not_set",
            "status_label": "No limit set",
        }
    remaining = limit - spent
    raw_percentage_used = float((spent / limit) * Decimal("100"))
    percentage_used = max(0.0, min(100.0, raw_percentage_used))
    if remaining < 0:
        status = "exceeded"
        label = f"Over budget by ₹{abs(float(remaining)):.2f}"
    elif raw_percentage_used >= 90:
        status = "near_limit"
        label = f"Near limit · ₹{float(remaining):.2f} left"
    elif raw_percentage_used >= 70:
        status = "warning"
        label = f"Watch closely · ₹{float(remaining):.2f} left"
    else:
        status = "ok"
        label = f"Within budget · ₹{float(remaining):.2f} left"
    return {
        "category": category,
        "spent": float(spent),
        "limit": float(limit),
        "remaining": float(remaining),
        "percentage_used": round(percentage_used, 2),
        "status": status,
        "status_label": label,
    }


def calculate_spending_by_category(transactions: list[Transaction]) -> dict[str, Decimal]:
    """Return current-month debit spending grouped by category."""
    spending: dict[str, Decimal] = {}
    for transaction in transactions:
        if not is_debit_transaction(transaction) or bool(getattr(transaction, "is_refund", False)) or bool(getattr(transaction, "is_anomaly", False)):
            continue
        if is_high_value_or_anomaly(transaction):
            continue
        category = str(getattr(transaction, "category", None) or "Miscellaneous")
        spending[category] = spending.get(category, Decimal("0")) + transaction_amount_abs(transaction)
    return spending


def calculate_savings_progress(transactions: list[Transaction], savings_target: Decimal | None) -> dict[str, Any]:
    """Calculate savings progress from savings-category credits and debits."""
    saved = Decimal("0")
    for transaction in transactions:
        category = str(getattr(transaction, "category", "") or "")
        if category != "Investments & Savings":
            continue
        saved += transaction_amount_abs(transaction)
    target = savings_target or Decimal("0")
    raw_percentage = float((saved / target) * Decimal("100")) if target > 0 else 0.0
    percentage = max(0.0, min(100.0, raw_percentage))
    return {
        "saved": float(saved),
        "target": float(target),
        "remaining": float(target - saved) if target else None,
        "percentage_used": round(percentage, 2),
        "status": "achieved" if target > 0 and saved >= target else "in_progress" if target > 0 else "not_set",
    }


def suggest_budget_from_transactions(transactions: list[Transaction], budget: UserBudget | None = None) -> dict[str, Any]:
    """Return suggested monthly limits that fit inside the total spending budget."""
    spending = calculate_spending_by_category(transactions)
    income = Decimal(str(total_credit_received(transactions)))
    if income <= 0:
        income = Decimal(str(estimate_income(transactions)))

    if income > 0:
        total_limit = (income * Decimal("0.70")).quantize(Decimal("1"))
        savings_target = (income * Decimal("0.20")).quantize(Decimal("1"))
    else:
        historical_total = sum(spending.get(category, Decimal("0")) for category in BUDGET_FIELD_TO_CATEGORY.values())
        total_limit = (historical_total * Decimal("0.75")).quantize(Decimal("1")) if historical_total > 0 else Decimal("0")
        savings_target = Decimal(str(getattr(budget, "savings_target", 0) or 0))

    tracked_spend = sum(spending.get(category, Decimal("0")) for category in BUDGET_FIELD_TO_CATEGORY.values())
    suggested: dict[str, float] = {}
    allocated = Decimal("0")
    fields = list(BUDGET_FIELD_TO_CATEGORY.items())
    for index, (field, category) in enumerate(fields):
        spent = spending.get(category, Decimal("0"))
        if total_limit <= 0 or tracked_spend <= 0 or spent <= 0:
            value = Decimal("0")
        elif index == len(fields) - 1:
            value = max(Decimal("0"), total_limit - allocated)
        else:
            value = ((spent / tracked_spend) * total_limit).quantize(Decimal("1"))
            allocated += value
        suggested[field] = float(value)
    suggested["total_monthly_limit"] = float(total_limit)
    suggested["savings_target"] = float(savings_target)
    suggested["suggestion_basis"] = "income_based" if income > 0 else "spend_based"
    suggested["tracked_spend"] = float(tracked_spend)
    return suggested


def get_budget_status(db: Session, user_id: UUID, month: str | None = None) -> dict[str, Any]:
    """Return selected-month spending status against the authenticated user's budget."""
    try:
        warnings: list[str] = []
        budget = db.query(UserBudget).filter(UserBudget.user_id == user_id).first()
        transactions, month_key = get_month_transactions(db, user_id, month)
        available_months = available_transaction_months(db, user_id)
        if not transactions:
            warnings.append("No transactions found for the current month.")
        spending_by_category = calculate_spending_by_category(transactions)
        suggested_budget = suggest_budget_from_transactions(transactions, budget)

        category_status: list[dict[str, Any]] = []
        for field, category in BUDGET_FIELD_TO_CATEGORY.items():
            limit = getattr(budget, field, None) if budget is not None else None
            limit_decimal = Decimal(str(limit)) if limit is not None else None
            category_status.append(build_budget_status(category, limit_decimal, spending_by_category.get(category, Decimal("0"))))

        custom_budgets = budget.custom_budgets if budget is not None else {}
        if isinstance(custom_budgets, dict):
            for category, amount in custom_budgets.items():
                limit = decimal_or_none(amount)
                if limit is None:
                    continue
                category_status.append(build_budget_status(str(category), limit, spending_by_category.get(str(category), Decimal("0"))))

        total_spent = sum(spending_by_category.values(), Decimal("0"))
        total_limit = Decimal(str(budget.total_monthly_limit)) if budget is not None and budget.total_monthly_limit is not None else None
        total_status = build_budget_status("Total Monthly Limit", total_limit, total_spent)
        total_overspend = float(total_spent - total_limit) if total_limit is not None else None
        required_reduction_pct = float(((total_spent - total_limit) / total_spent) * Decimal("100")) if total_limit is not None and total_spent > total_limit and total_spent > 0 else 0.0
        savings_progress = calculate_savings_progress(transactions, Decimal(str(budget.savings_target)) if budget is not None and budget.savings_target is not None else None)
        if budget is None:
            warnings = ["No budget has been set yet."]

        return {
            "data": {
                "budget": serialize_budget(budget),
                "month": month_key,
                "available_months": available_months,
                "category_status": category_status,
                "total_status": total_status,
                "savings_progress": savings_progress,
                "suggested_budget": suggested_budget,
                "selected_month_spend": float(total_spent),
                "monthly_limit_gap": total_overspend,
                "required_reduction_pct": round(required_reduction_pct, 2),
                "has_budget": budget is not None,
            },
            "warnings": list(dict.fromkeys(warnings)),
        }
    except ValueError as exc:
        return {"data": None, "warnings": [], "error": {"code": "INVALID_BUDGET", "message": str(exc), "details": {}}}
    except SQLAlchemyError as exc:
        return {"data": None, "warnings": [], "error": {"code": "DATABASE_ERROR", "message": "Database operation failed.", "details": {"error_type": exc.__class__.__name__}}}


def safe_budget_operation(operation_name: str, callback: Any) -> dict[str, Any]:
    """Run a budget callback and convert known failures into structured service responses."""
    try:
        return callback()
    except ValueError as exc:
        return {"data": None, "warnings": [], "error": {"code": "INVALID_BUDGET", "message": str(exc), "details": {"operation": operation_name}}}
    except SQLAlchemyError as exc:
        return {
            "data": None,
            "warnings": [],
            "error": {"code": "DATABASE_ERROR", "message": "Database operation failed.", "details": {"error_type": exc.__class__.__name__}},
        }
