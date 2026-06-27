"""Transaction API routes for category correction and transaction updates."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import LearnedMerchantRule, MerchantDiscoveryCache, Transaction, TransactionCategoryFeedback, User, UserCategoryRule
from schemas.common import error_response, success_response
from services.merchant_intelligence import ALLOWED_CATEGORIES, get_need_want_waste_type, normalize_merchant
from services.security import verify_statement_ownership

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


class CategoryCorrectionRequest(BaseModel):
    """Request body for correcting a transaction category."""

    category: str = Field(..., min_length=1, max_length=120)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        """Validate that the category is part of the canonical category list."""
        cleaned_value = value.strip()
        if cleaned_value not in ALLOWED_CATEGORIES:
            raise ValueError("category must be one of the supported MoneyLeak AI categories")
        return cleaned_value


class CategoryRuleRequest(BaseModel):
    """Request body for managing user merchant category rules."""

    merchant_normalized: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=120)
    apply_to_existing: bool = False

    @field_validator("merchant_normalized")
    @classmethod
    def validate_merchant(cls, value: str) -> str:
        """Normalize merchant input for consistent matching."""
        normalized = normalize_merchant(value)
        if not normalized:
            raise ValueError("merchant_normalized is required")
        return normalized

    @field_validator("category")
    @classmethod
    def validate_rule_category(cls, value: str) -> str:
        """Validate a correction rule category."""
        cleaned_value = value.strip()
        if cleaned_value not in ALLOWED_CATEGORIES:
            raise ValueError("category must be one of the supported MoneyLeak AI categories")
        return cleaned_value


def json_safe(value: Any) -> Any:
    """Convert common ORM scalar values into JSON-safe values."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def serialize_transaction(transaction: Transaction) -> dict[str, Any]:
    """Serialize a Transaction ORM object into API response data."""
    return {
        "id": json_safe(transaction.id),
        "user_id": json_safe(transaction.user_id),
        "statement_id": json_safe(transaction.statement_id),
        "transaction_date": json_safe(transaction.transaction_date),
        "transaction_time": json_safe(transaction.transaction_time),
        "description": transaction.description,
        "merchant": transaction.merchant,
        "amount": json_safe(transaction.amount),
        "transaction_type": getattr(transaction.transaction_type, "value", transaction.transaction_type),
        "category": transaction.category,
        "category_confidence": transaction.category_confidence,
        "category_source": transaction.category_source,
        "is_subscription": transaction.is_subscription,
        "is_duplicate": transaction.is_duplicate,
        "is_small_spend": transaction.is_small_spend,
        "is_anomaly": transaction.is_anomaly,
        "is_refund": transaction.is_refund,
        "is_cashback": transaction.is_cashback,
        "is_late_night": transaction.is_late_night,
        "needs_review": transaction.needs_review,
        "need_want_waste_type": getattr(transaction.need_want_waste_type, "value", transaction.need_want_waste_type),
        "created_at": json_safe(transaction.created_at),
    }


def serialize_category_rule(rule: UserCategoryRule) -> dict[str, Any]:
    """Serialize a user category rule for API responses."""
    return {
        "id": json_safe(rule.id),
        "user_id": json_safe(rule.user_id),
        "merchant_normalized": rule.merchant_normalized,
        "category": rule.category,
        "created_at": json_safe(rule.created_at),
    }


def get_transaction_for_user(db: Session, transaction_id: UUID, user_id: UUID) -> Transaction | None:
    """Return a transaction that belongs to the authenticated user."""
    return db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.user_id == user_id).first()


def upsert_user_category_rule(db: Session, user_id: UUID, merchant_normalized: str, category: str) -> UserCategoryRule | None:
    """Create or update a user-specific category rule for a merchant."""
    if not merchant_normalized:
        return None
    rule = (
        db.query(UserCategoryRule)
        .filter(UserCategoryRule.user_id == user_id, UserCategoryRule.merchant_normalized == merchant_normalized)
        .first()
    )
    if rule is None:
        rule = UserCategoryRule(user_id=user_id, merchant_normalized=merchant_normalized, category=category)
        db.add(rule)
    else:
        rule.category = category
    return rule


def upsert_transaction_feedback(
    db: Session,
    transaction: Transaction,
    merchant_normalized: str,
    previous_category: str | None,
    corrected_category: str,
) -> TransactionCategoryFeedback:
    """Create or update transaction-level category feedback for learning."""
    feedback = (
        db.query(TransactionCategoryFeedback)
        .filter(TransactionCategoryFeedback.transaction_id == transaction.id)
        .first()
    )
    if feedback is None:
        feedback = TransactionCategoryFeedback(
            transaction_id=transaction.id,
            user_id=transaction.user_id,
            merchant_normalized=merchant_normalized,
            previous_category=previous_category,
            corrected_category=corrected_category,
        )
        db.add(feedback)
    else:
        feedback.merchant_normalized = merchant_normalized
        feedback.previous_category = previous_category
        feedback.corrected_category = corrected_category
    return feedback


def count_distinct_user_corrections(db: Session, merchant_normalized: str, category: str) -> int:
    """Count distinct users who corrected a merchant to the same category."""
    result = (
        db.query(func.count(func.distinct(TransactionCategoryFeedback.user_id)))
        .filter(
            TransactionCategoryFeedback.merchant_normalized == merchant_normalized,
            TransactionCategoryFeedback.corrected_category == category,
        )
        .scalar()
    )
    return int(result or 0)


def upsert_learned_rule_if_ready(db: Session, merchant_normalized: str, category: str) -> LearnedMerchantRule | None:
    """Create or update a global learned merchant rule after three distinct user corrections."""
    if not merchant_normalized:
        return None
    correction_count = count_distinct_user_corrections(db, merchant_normalized, category)
    if correction_count < 3:
        return None
    confidence = min(0.9, 0.5 + (correction_count * 0.1))
    learned_rule = (
        db.query(LearnedMerchantRule)
        .filter(LearnedMerchantRule.merchant_normalized == merchant_normalized)
        .first()
    )
    if learned_rule is None:
        learned_rule = LearnedMerchantRule(
            merchant_normalized=merchant_normalized,
            category=category,
            correction_count=correction_count,
            confidence=confidence,
        )
        db.add(learned_rule)
    else:
        learned_rule.category = category
        learned_rule.correction_count = correction_count
        learned_rule.confidence = confidence
    return learned_rule



def clear_stale_merchant_cache(db: Session, merchant_normalized: str, corrected_category: str) -> int:
    """Delete cached merchant discovery rows whose category conflicts with a user correction."""
    if not merchant_normalized:
        return 0
    stale_rows = (
        db.query(MerchantDiscoveryCache)
        .filter(
            MerchantDiscoveryCache.normalized_merchant_name == merchant_normalized,
            MerchantDiscoveryCache.category != corrected_category,
        )
        .all()
    )
    deleted_count = len(stale_rows)
    for row in stale_rows:
        db.delete(row)
    return deleted_count

def apply_category_correction(transaction: Transaction, category: str) -> None:
    """Apply corrected category fields to a transaction ORM object."""
    transaction.category = category
    transaction.category_confidence = 1.0
    transaction.category_source = "user_rule"
    transaction.needs_review = False
    transaction.need_want_waste_type = get_need_want_waste_type(category)


def apply_rule_to_existing_transactions(db: Session, user_id: UUID, merchant_normalized: str, category: str) -> int:
    """Apply a saved user rule to matching existing transactions."""
    transactions = db.query(Transaction).filter(Transaction.user_id == user_id).all()
    applied_count = 0
    for transaction in transactions:
        candidate = normalize_merchant(transaction.merchant or transaction.description or "")
        if candidate == merchant_normalized:
            apply_category_correction(transaction, category)
            applied_count += 1
    return applied_count


@router.get("/category-rules", response_model=None)
def list_category_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """List saved merchant category rules for the authenticated user."""
    try:
        rules = (
            db.query(UserCategoryRule)
            .filter(UserCategoryRule.user_id == current_user.id)
            .order_by(UserCategoryRule.created_at.desc())
            .all()
        )
        return success_response({"rules": [serialize_category_rule(rule) for rule in rules]}, [])
    except SQLAlchemyError as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("DATABASE_ERROR", "Database operation failed.", {"error_type": exc.__class__.__name__}),
        )


@router.post("/category-rules", response_model=None)
def create_or_update_category_rule(
    payload: CategoryRuleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Create or update a user merchant category rule."""
    try:
        rule = upsert_user_category_rule(db, current_user.id, payload.merchant_normalized, payload.category)
        applied_count = 0
        if payload.apply_to_existing:
            applied_count = apply_rule_to_existing_transactions(db, current_user.id, payload.merchant_normalized, payload.category)
        db.commit()
        if rule is not None:
            db.refresh(rule)
        return success_response({"rule": serialize_category_rule(rule), "applied_count": applied_count}, [])
    except SQLAlchemyError as exc:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("DATABASE_ERROR", "Database operation failed.", {"error_type": exc.__class__.__name__}),
        )


@router.post("/category-rules/{rule_id}/apply", response_model=None)
def apply_category_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Apply a saved category rule to existing matching transactions."""
    try:
        rule = db.query(UserCategoryRule).filter(UserCategoryRule.id == rule_id, UserCategoryRule.user_id == current_user.id).first()
        if rule is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error_response("CATEGORY_RULE_NOT_FOUND", "Category rule was not found.", {}),
            )
        applied_count = apply_rule_to_existing_transactions(db, current_user.id, rule.merchant_normalized, rule.category)
        db.commit()
        return success_response({"rule": serialize_category_rule(rule), "applied_count": applied_count}, [])
    except SQLAlchemyError as exc:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("DATABASE_ERROR", "Database operation failed.", {"error_type": exc.__class__.__name__}),
        )


@router.delete("/category-rules/{rule_id}", response_model=None)
def delete_category_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Delete a saved user category rule."""
    try:
        rule = db.query(UserCategoryRule).filter(UserCategoryRule.id == rule_id, UserCategoryRule.user_id == current_user.id).first()
        if rule is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error_response("CATEGORY_RULE_NOT_FOUND", "Category rule was not found.", {}),
            )
        db.delete(rule)
        db.commit()
        return success_response({"deleted": True, "rule_id": str(rule_id)}, [])
    except SQLAlchemyError as exc:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("DATABASE_ERROR", "Database operation failed.", {"error_type": exc.__class__.__name__}),
        )


@router.patch("/{transaction_id}/category", response_model=None)
def update_transaction_category(
    transaction_id: UUID,
    payload: CategoryCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Correct a transaction category, save user memory, store feedback, and update learned rules when ready."""
    try:
        transaction = get_transaction_for_user(db, transaction_id, current_user.id)
        if transaction is None:
            existing_transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
            if existing_transaction is not None:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content=error_response("FORBIDDEN", "You do not have access to this transaction.", {}),
                )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error_response("TRANSACTION_NOT_FOUND", "Transaction was not found.", {}),
            )

        previous_category = transaction.category
        merchant_normalized = normalize_merchant(transaction.merchant or transaction.description or "")
        apply_category_correction(transaction, payload.category)
        upsert_user_category_rule(db, current_user.id, merchant_normalized, payload.category)
        upsert_transaction_feedback(db, transaction, merchant_normalized, previous_category, payload.category)
        clear_stale_merchant_cache(db, merchant_normalized, payload.category)
        db.flush()
        upsert_learned_rule_if_ready(db, merchant_normalized, payload.category)
        db.commit()
        db.refresh(transaction)
        return success_response({"transaction": serialize_transaction(transaction)}, [])
    except SQLAlchemyError as exc:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("DATABASE_ERROR", "Database operation failed.", {"error_type": exc.__class__.__name__}),
        )

@router.get("", response_model=None)
def list_transactions(
    statement_id: UUID | None = None,
    category: str | None = None,
    transaction_type: str | None = None,
    limit: int = 5000,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """List transactions for the authenticated user with total-count aware pagination."""
    try:
        query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
        if statement_id is not None:
            verify_statement_ownership(db, current_user.id, statement_id)
            query = query.filter(Transaction.statement_id == statement_id)
        if category:
            query = query.filter(Transaction.category == category)
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type.lower())
        total_count = query.count()
        safe_limit = min(max(int(limit or 5000), 1), 10000)
        safe_offset = max(int(offset or 0), 0)
        transactions = query.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc()).offset(safe_offset).limit(safe_limit).all()
        return success_response(
            {
                "transactions": [serialize_transaction(transaction) for transaction in transactions],
                "total": total_count,
                "returned": len(transactions),
                "limit": safe_limit,
                "offset": safe_offset,
            },
            [],
        )
    except SQLAlchemyError as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("DATABASE_ERROR", "Database operation failed.", {"error_type": exc.__class__.__name__}),
        )
