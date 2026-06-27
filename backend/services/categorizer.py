"""Hybrid rule-first categorization engine for MoneyLeak AI transactions."""

from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import LearnedMerchantRule, MerchantDiscoveryCache, Transaction, UserCategoryRule
from services.ai_merchant_discovery import discover_merchant
from services.merchant_intelligence import (
    contains_verified_match,
    digit_only_transfer_match,
    exact_verified_match,
    fuzzy_verified_match,
    get_need_want_waste_type,
    is_refund_description,
    keyword_category_match,
    normalize_merchant,
    text_for_matching,
)

logger = logging.getLogger("moneyleak-ai.categorizer")
MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "models" / "category_model.pkl"


def build_result(
    category: str,
    confidence: float,
    source: str,
    needs_review: bool,
    classification_reason: str,
    is_refund: bool = False,
    is_anomaly: bool = False,
) -> dict[str, Any]:
    """Build a consistent categorization response payload."""
    return {
        "category": category,
        "confidence": round(float(confidence), 4),
        "source": source,
        "needs_review": bool(needs_review),
        "classification_reason": classification_reason,
        "need_want_waste_type": get_need_want_waste_type(category),
        "is_refund": bool(is_refund),
        "is_anomaly": bool(is_anomaly),
    }


def contains_any_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    """Return True when normalized text contains any pattern as a word-like match."""
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def categorize_credit_transaction(description: str, combined_text: str, refund_flag: bool) -> dict[str, Any] | None:
    """Categorize incoming credit transactions before debit merchant rules are applied."""
    text = combined_text.lower()
    if refund_flag or contains_any_pattern(text, (r"\brefund\b", r"\breversal\b", r"\bcashback\b", r"cash back", r"\bchargeback\b")):
        return build_result("Refund/Cashback", 0.9, "keyword_rule", False, "Credit matched refund, reversal, cashback, or chargeback language", is_refund=True)
    if contains_any_pattern(text, (r"\bsalary\b", r"\bpayroll\b", r"\bstipend\b", r"\bwages\b", r"\bemployer\b")):
        return build_result("Income", 0.95, "keyword_rule", False, "Credit matched salary or payroll income language", is_refund=False)
    if contains_any_pattern(text, (r"\bfreelance\b", r"\bclient payment\b", r"\binvoice payment\b", r"\bconsulting fee\b")):
        return build_result("Income", 0.88, "keyword_rule", False, "Credit matched freelance or client-payment income language", is_refund=False)
    if contains_any_pattern(text, (r"\bloan disbursal\b", r"\bloan disbursement\b", r"\bdisbursal credit\b")):
        return build_result("Loan Credit", 0.72, "keyword_rule", True, "Credit looks like loan disbursal and should be reviewed separately", is_refund=False)
    if contains_any_pattern(text, (r"\binvestment redemption\b", r"\bredemption\b", r"\bwithdrawal credit\b", r"\bmutual fund redemption\b")):
        return build_result("Investment Withdrawal", 0.78, "keyword_rule", True, "Credit looks like investment redemption and should not be treated as income", is_refund=False)
    return build_result("Credit", 0.45, "low_confidence", True, "Incoming credit did not match income, refund, loan, or investment rules", is_refund=False)


def transfer_rule_match(combined_text: str) -> bool:
    """Return True when text clearly represents an Indian bank or UPI transfer rail."""
    text = combined_text.lower()
    return bool(
        re.search(r"\b(imps|neft|rtgs|p2a|p2m|p2p|okhdfc|okaxis|oksbi)\b", text)
        or re.search(r"\b(transfer to|sent to|paid to)\b", text)
        or re.search(r"\bupi[/\\:-]?(p2a|p2m|p2p|[6-9]\d{9})\b", text)
        or re.search(r"\bupi[/\\:-].*[/\\:-](okhdfc|okaxis|oksbi)\b", text)
    )


def balance_anomaly_match(combined_text: str) -> bool:
    """Return True when a transaction is a balance/anomaly test row or negative-balance marker."""
    text = combined_text.lower()
    return bool(re.search(r"negative\s+balance|balance\s+anomaly", text))


def investment_debit_rule_match(combined_text: str) -> bool:
    """Return True when a debit transaction clearly represents investing or savings movement."""
    text = combined_text.lower()
    return bool(
        re.search(r"\b(paytm money|zerodha|groww|hdfc securities|sbi mf|mutual fund|sip|investment|securities|fund transfer)\b", text)
        and not re.search(r"\b(redemption|withdrawal credit|refund|cashback|reversal|chargeback)\b", text)
    )


def parse_uuid(value: str | UUID | None) -> UUID | None:
    """Parse a UUID value safely and return None when parsing fails."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None


def get_user_rule(db: Session | None, user_id: str | UUID | None, merchant_normalized: str) -> UserCategoryRule | None:
    """Return a matching user category rule when it exists."""
    parsed_user_id = parse_uuid(user_id)
    if db is None or parsed_user_id is None or not merchant_normalized:
        return None
    try:
        return (
            db.query(UserCategoryRule)
            .filter(
                UserCategoryRule.user_id == parsed_user_id,
                UserCategoryRule.merchant_normalized == merchant_normalized,
            )
            .first()
        )
    except SQLAlchemyError as exc:
        logger.warning("User rule lookup failed: %s", exc.__class__.__name__)
        return None


def get_learned_rule(db: Session | None, merchant_normalized: str) -> LearnedMerchantRule | None:
    """Return a global learned merchant rule when it is mature enough."""
    if db is None or not merchant_normalized:
        return None
    try:
        rule = (
            db.query(LearnedMerchantRule)
            .filter(LearnedMerchantRule.merchant_normalized == merchant_normalized)
            .first()
        )
        if rule is not None and int(rule.correction_count or 0) >= 3:
            return rule
        return None
    except SQLAlchemyError as exc:
        logger.warning("Learned rule lookup failed: %s", exc.__class__.__name__)
        return None


def get_cached_discovery(db: Session | None, merchant_normalized: str, city: str | None) -> MerchantDiscoveryCache | None:
    """Return a city-aware cached merchant discovery record when it is confident enough."""
    if db is None or not merchant_normalized:
        return None
    try:
        query = db.query(MerchantDiscoveryCache).filter(
            MerchantDiscoveryCache.normalized_merchant_name == merchant_normalized,
            MerchantDiscoveryCache.confidence_score >= 0.7,
        )
        city_value = str(city).strip() if city else None
        if city_value:
            query = query.filter(MerchantDiscoveryCache.city == city_value)
        return query.order_by(MerchantDiscoveryCache.confidence_score.desc()).first()
    except SQLAlchemyError as exc:
        logger.warning("Merchant cache lookup failed: %s", exc.__class__.__name__)
        return None


def load_ml_model() -> Any | None:
    """Load the optional category ML model or return None when unavailable."""
    model_path = Path(MODEL_PATH)
    if not model_path.exists():
        logger.warning("Category ML model missing at %s; skipping ML fallback", model_path)
        return None
    try:
        with model_path.open("rb") as model_file:
            return pickle.load(model_file)
    except (OSError, pickle.PickleError, AttributeError, EOFError, ImportError, ValueError) as exc:
        logger.warning("Category ML model load failed: %s", exc.__class__.__name__)
        return None


def predict_with_model(model: Any, transaction: dict[str, Any]) -> tuple[str, float] | None:
    """Return a model category prediction and confidence when the model supports it."""
    text = text_for_matching(transaction)
    if not text:
        return None
    try:
        prediction = model.predict([text])[0]
        confidence = 0.0
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba([text])[0]
            confidence = float(max(probabilities))
        else:
            confidence = 0.61
        return str(prediction), confidence
    except (AttributeError, IndexError, TypeError, ValueError) as exc:
        logger.warning("Category ML prediction failed: %s", exc.__class__.__name__)
        return None


def categorize_transaction(transaction: dict[str, Any], user_id: str, city: str | None = None, db: Session | None = None) -> dict[str, Any]:
    """Categorize a transaction using user rules, verified rules, learned rules, cache, fuzzy, keywords, and ML fallback."""
    merchant = str(transaction.get("merchant") or "").strip()
    description = str(transaction.get("description") or "").strip()
    merchant_normalized = normalize_merchant(merchant)
    combined_text = text_for_matching(transaction)
    refund_flag = is_refund_description(description)

    amount = abs(float(transaction.get("amount") or 0.0))
    transaction_type = str(transaction.get("transaction_type") or "").lower()
    if transaction_type == "credit":
        return categorize_credit_transaction(description, combined_text, refund_flag)

    if transaction_type == "debit" and (amount > 1_000_000.0 or balance_anomaly_match(combined_text)):
        reason = "Debit amount is above ₹10,00,000 and must be reviewed before normal categorization"
        if balance_anomaly_match(combined_text) and amount <= 1_000_000.0:
            reason = "Transaction indicates a balance anomaly and must be reviewed before normal analytics"
        return build_result(
            category="Miscellaneous",
            confidence=0.1,
            source="high_value_review",
            needs_review=True,
            classification_reason=reason,
            is_refund=refund_flag,
            is_anomaly=True,
        )

    user_rule = get_user_rule(db, user_id, merchant_normalized)
    if user_rule is not None:
        return build_result(
            category=user_rule.category,
            confidence=1.0,
            source="user_rule",
            needs_review=False,
            classification_reason=f"Merchant '{merchant}' matched user's saved correction rule",
            is_refund=refund_flag,
        )

    exact_match = exact_verified_match(merchant_normalized)
    if exact_match is not None:
        matched_keyword, category = exact_match
        return build_result(
            category=category,
            confidence=0.95,
            source="verified_merchant",
            needs_review=False,
            classification_reason=f"Merchant '{matched_keyword.title()}' matched verified rule",
            is_refund=refund_flag,
        )

    contains_match = contains_verified_match(merchant_normalized)
    if contains_match is not None:
        matched_keyword, category = contains_match
        return build_result(
            category=category,
            confidence=0.9,
            source="verified_merchant",
            needs_review=False,
            classification_reason=f"Merchant '{merchant}' contained verified keyword '{matched_keyword}'",
            is_refund=refund_flag,
        )

    if investment_debit_rule_match(combined_text):
        return build_result(
            category="Investments & Savings",
            confidence=0.9,
            source="keyword_rule",
            needs_review=False,
            classification_reason="Transaction matched investing, SIP, securities, or savings movement language",
            is_refund=refund_flag,
        )

    if digit_only_transfer_match(merchant_normalized, description) and not re.search(r"\b(okhdfc|okaxis|oksbi|p2a|p2m|p2p)\b", combined_text.lower()):
        return build_result(
            category="Transfers",
            confidence=0.35,
            source="keyword_rule",
            needs_review=True,
            classification_reason="Merchant looked like a phone-number transfer and requires review",
            is_refund=refund_flag,
        )

    if transfer_rule_match(combined_text):
        merchant_unknown = merchant_normalized in {"", "unknown"} or bool(re.fullmatch(r"[0-9]+", merchant_normalized))
        return build_result(
            category="Transfers",
            confidence=0.75,
            source="keyword_rule",
            needs_review=merchant_unknown,
            classification_reason="Transaction matched UPI, IMPS, NEFT, RTGS, or transfer language",
            is_refund=refund_flag,
        )

    if digit_only_transfer_match(merchant_normalized, description):
        return build_result(
            category="Transfers",
            confidence=0.75,
            source="keyword_rule",
            needs_review=True,
            classification_reason="Merchant looked like a phone-number transfer and requires review",
            is_refund=refund_flag,
        )

    learned_rule = get_learned_rule(db, merchant_normalized)
    if learned_rule is not None:
        return build_result(
            category=learned_rule.category,
            confidence=float(learned_rule.confidence or 0.8),
            source="learned_rule",
            needs_review=False,
            classification_reason=f"Merchant '{merchant}' matched global learned rule from corrections",
            is_refund=refund_flag,
        )

    cached_discovery = get_cached_discovery(db, merchant_normalized, city)
    if cached_discovery is not None:
        return build_result(
            category=cached_discovery.category,
            confidence=float(cached_discovery.confidence_score or 0.7),
            source="merchant_cache",
            needs_review=False,
            classification_reason=f"Merchant '{merchant}' matched cached discovery for city-aware merchant intelligence",
            is_refund=refund_flag,
        )

    atm_keyword_match = keyword_category_match(combined_text) if "atm" in combined_text.lower() or "cash withdrawal" in combined_text.lower() else None
    if atm_keyword_match is not None and atm_keyword_match[1] == "Cash Withdrawal":
        pattern, category = atm_keyword_match
        return build_result(
            category=category,
            confidence=0.75,
            source="keyword_rule",
            needs_review=False,
            classification_reason=f"Description matched keyword rule '{pattern}'",
            is_refund=refund_flag,
        )

    fuzzy_match = fuzzy_verified_match(merchant_normalized)
    if fuzzy_match is not None:
        matched_keyword, category, score = fuzzy_match
        return build_result(
            category=category,
            confidence=score / 100.0,
            source="fuzzy_match",
            needs_review=False,
            classification_reason=f"Merchant '{merchant}' fuzzy matched verified merchant '{matched_keyword}' with score {score:.0f}",
            is_refund=refund_flag,
        )

    keyword_match = keyword_category_match(combined_text)
    if keyword_match is not None:
        pattern, category = keyword_match
        return build_result(
            category=category,
            confidence=0.75,
            source="keyword_rule",
            needs_review=False,
            classification_reason=f"Description matched keyword rule '{pattern}'",
            is_refund=refund_flag,
        )

    try:
        from ml.predict_category import predict_category

        model_result = predict_category(transaction)
        if bool(model_result.get("available", False)) and float(model_result.get("confidence") or 0.0) > 0.6:
            predicted_category = str(model_result.get("category") or "Miscellaneous")
            return build_result(
                category=predicted_category,
                confidence=float(model_result.get("confidence") or 0.0),
                source="ml_fallback",
                needs_review=False,
                classification_reason="Optional ML fallback predicted category above confidence threshold",
                is_refund=refund_flag,
            )
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        logger.warning("Optional category ML fallback failed: %s", exc.__class__.__name__)

    if merchant_normalized:
        discovery = discover_merchant(merchant, city, db)
        if bool(discovery.get("success", False)):
            discovery_data = discovery.get("data", {}) if isinstance(discovery.get("data", {}), dict) else {}
            discovered_category = str(discovery_data.get("category") or "Miscellaneous")
            if discovered_category != "Miscellaneous":
                return build_result(
                    category=discovered_category,
                    confidence=0.55,
                    source="merchant_cache",
                    needs_review=False,
                    classification_reason=f"Merchant '{merchant}' was categorized by AI merchant discovery",
                    is_refund=refund_flag,
                )

    return build_result(
        category="Miscellaneous",
        confidence=0.1,
        source="low_confidence",
        needs_review=True,
        classification_reason=f"No reliable category rule matched merchant '{merchant or 'Unknown'}'",
        is_refund=refund_flag,
    )


def serialize_transaction_for_categorization(transaction: Transaction) -> dict[str, Any]:
    """Serialize an ORM transaction into the categorizer input shape."""
    return {
        "merchant": transaction.merchant,
        "description": transaction.description,
        "amount": float(transaction.amount or 0),
        "transaction_type": getattr(transaction.transaction_type, "value", transaction.transaction_type),
        "transaction_date": transaction.transaction_date.isoformat() if transaction.transaction_date else None,
    }


def apply_categorization_to_transaction(transaction: Transaction, categorization: dict[str, Any]) -> None:
    """Mutate a transaction ORM object with categorization output fields."""
    transaction.category = str(categorization.get("category") or "Miscellaneous")
    transaction.category_confidence = float(categorization.get("confidence") or 0.0)
    transaction.category_source = str(categorization.get("source") or "low_confidence")
    transaction.needs_review = bool(categorization.get("needs_review", False))
    transaction.need_want_waste_type = str(categorization.get("need_want_waste_type") or "unknown")
    if bool(categorization.get("is_refund", False)):
        transaction.is_refund = True
    if bool(categorization.get("is_anomaly", False)):
        transaction.is_anomaly = True


def categorize_statement(statement_id: str, user_id: str, db: Session) -> dict[str, Any]:
    """Categorize all uncategorized transactions for a statement without one bad row stopping the batch."""
    parsed_statement_id = parse_uuid(statement_id)
    parsed_user_id = parse_uuid(user_id)
    if parsed_statement_id is None or parsed_user_id is None:
        raise ValueError("statement_id and user_id must be valid UUID values")

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.statement_id == parsed_statement_id,
            Transaction.user_id == parsed_user_id,
            Transaction.category == "Miscellaneous",
        )
        .all()
    )
    updated_count = 0
    errors: list[dict[str, Any]] = []
    for transaction in transactions:
        try:
            categorization = categorize_transaction(
                serialize_transaction_for_categorization(transaction),
                user_id=str(parsed_user_id),
                db=db,
            )
            apply_categorization_to_transaction(transaction, categorization)
            updated_count += 1
        except (SQLAlchemyError, AttributeError, TypeError, ValueError) as exc:
            errors.append({"transaction_id": str(transaction.id), "error_type": exc.__class__.__name__})
            logger.warning("Transaction categorization failed: %s", exc.__class__.__name__)
    db.commit()
    return {"statement_id": str(parsed_statement_id), "updated_count": updated_count, "errors": errors}
