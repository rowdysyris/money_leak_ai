"""Insights analytics API routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import User
from routers.dashboard import database_error_response, fetch_transactions_for_statement, no_statement_payload, service_to_response
from services.burn_rate_analyzer import analyze_burn_rate
from services.dashboard_service import get_category_breakdown
from services.duplicate_detector import detect_duplicates
from services.leakage_detector import detect_small_spend_leakage
from services.merchant_analyzer import analyze_late_night_spending, compare_weekend_vs_weekday, get_yearly_impact
from services.money_leak_score import calculate_score
from services.monthly_analysis import calculate_monthly_analysis, calculate_monthly_comparison
from services.financial_health import calculate_health_score
from services.monthly_explainer import explain_latest_month_change
from services.merchant_risk import top_merchant_risks
from services.report_summary import classify_personality, generate_saving_priority
from services.smart_alerts import detect_bill_reminders, detect_refund_reversal_tracking, detect_smart_alerts
from services.subscription_detector import detect_subscriptions

router = APIRouter(prefix="/api/insights", tags=["Insights"])


def load_insight_inputs(db: Session, user_id: UUID, statement_id: UUID | None) -> tuple[bool, list[Any]]:
    """Load transactions for an insight endpoint and report whether a statement exists."""
    statement, transactions = fetch_transactions_for_statement(db, user_id, statement_id)
    return statement is not None, transactions


def dependencies_for_score(transactions: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Calculate subscriptions and duplicates required by score and savings endpoints."""
    subscription_result = detect_subscriptions(transactions)
    duplicate_result = detect_duplicates(transactions)
    warnings = list(dict.fromkeys(subscription_result.get("warnings", []) + duplicate_result.get("warnings", [])))
    return subscription_result.get("data", []), duplicate_result.get("data", []), warnings


@router.get("/small-spend-leaks", response_model=None)
def small_spend_leaks(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return small-spend leakage buckets."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(detect_small_spend_leakage(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/subscriptions", response_model=None)
def subscriptions(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return detected recurring subscriptions."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(detect_subscriptions(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/duplicates", response_model=None)
def duplicates(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return detected duplicate payments."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(detect_duplicates(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/money-leak-score", response_model=None)
def money_leak_score(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return the composite money leak score."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        subscriptions_data, duplicates_data, dependency_warnings = dependencies_for_score(transactions)
        result = calculate_score(transactions, subscriptions_data, duplicates_data)
        result["warnings"] = list(dict.fromkeys(result.get("warnings", []) + dependency_warnings))
        return service_to_response(result)
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/saving-priority-list", response_model=None)
def saving_priority_list(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return ranked saving opportunities."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        subscriptions_data, duplicates_data, dependency_warnings = dependencies_for_score(transactions)
        result = generate_saving_priority(transactions, subscriptions_data, duplicates_data)
        result["warnings"] = list(dict.fromkeys(result.get("warnings", []) + dependency_warnings))
        return service_to_response(result)
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/month-end-survival", response_model=None)
def month_end_survival(
    statement_id: UUID | None = Query(default=None),
    current_balance: float | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return month-end survival projection."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        result = analyze_burn_rate(transactions, current_balance=current_balance)
        data = result.get("data", {})
        survival = {
            "days_until_empty": data.get("days_until_empty") if isinstance(data, dict) else None,
            "will_survive_month": data.get("will_survive_month") if isinstance(data, dict) else None,
            "monthly_projection": data.get("monthly_projection") if isinstance(data, dict) else 0.0,
            "remaining_days_in_month": data.get("remaining_days_in_month") if isinstance(data, dict) else 0,
        }
        return {"success": True, "data": survival, "warnings": result.get("warnings", [])}
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/daily-safe-limit", response_model=None)
def daily_safe_limit(
    statement_id: UUID | None = Query(default=None),
    current_balance: float | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return daily safe spending limit."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        result = analyze_burn_rate(transactions, current_balance=current_balance)
        data = result.get("data", {})
        safe_limit = {
            "daily_safe_limit": data.get("daily_safe_limit") if isinstance(data, dict) else None,
            "estimated_fixed_upcoming": data.get("estimated_fixed_upcoming") if isinstance(data, dict) else 0.0,
            "remaining_days_in_month": data.get("remaining_days_in_month") if isinstance(data, dict) else 0,
        }
        return {"success": True, "data": safe_limit, "warnings": result.get("warnings", [])}
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/spending-personality", response_model=None)
def spending_personality(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return deterministic spending personality classification."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        breakdown = get_category_breakdown(transactions)
        return service_to_response(classify_personality(transactions, breakdown))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/burn-rate", response_model=None)
def burn_rate(
    statement_id: UUID | None = Query(default=None),
    current_balance: float | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return full burn-rate analysis."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(analyze_burn_rate(transactions, current_balance=current_balance))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/yearly-impact", response_model=None)
def yearly_impact(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return all categories annualized."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(get_yearly_impact(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/merchant-addiction", response_model=None)
def merchant_addiction(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return the five merchants with the strongest repeat-spend risk."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return {"success": True, "data": top_merchant_risks(transactions), "warnings": []}
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/weekend-vs-weekday", response_model=None)
def weekend_vs_weekday(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return weekend versus weekday spending comparison."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(compare_weekend_vs_weekday(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/late-night-spending", response_model=None)
def late_night_spending(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return late-night spending analysis."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(analyze_late_night_spending(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/monthly-analysis", response_model=None)
def monthly_analysis(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return month-wise spending, income, leakage, and coverage analysis."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(calculate_monthly_analysis(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/monthly-comparison", response_model=None)
def monthly_comparison(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return month-over-month comparison and insights."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(calculate_monthly_comparison(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/financial-health-score", response_model=None)
def financial_health_score(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return income-aware financial health score and drivers."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(calculate_health_score(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/bill-reminders", response_model=None)
def bill_reminders(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return upcoming bill, EMI, rent, and subscription reminders."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(detect_bill_reminders(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/refund-reversal-tracking", response_model=None)
def refund_reversal_tracking(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return refund, reversal, failed-payment, and chargeback tracking."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(detect_refund_reversal_tracking(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/monthly-change-explanation", response_model=None)
def monthly_change_explanation(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return plain-English explanation of what changed in the latest month."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(explain_latest_month_change(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/smart-alerts", response_model=None)
def smart_alerts(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return combined smart alerts for bills and refund/reversal review."""
    try:
        has_statement, transactions = load_insight_inputs(db, current_user.id, statement_id)
        if not has_statement:
            return no_statement_payload()
        return service_to_response(detect_smart_alerts(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)
