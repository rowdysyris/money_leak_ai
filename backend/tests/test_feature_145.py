"""Tests for smart alerts, refund tracking, and month-change explanation."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from services.monthly_explainer import explain_latest_month_change
from services.smart_alerts import detect_bill_reminders, detect_refund_reversal_tracking, detect_smart_alerts


def tx(day: date, amount: float, kind: str, category: str, merchant: str, description: str | None = None):
    """Build a lightweight transaction object for feature tests."""
    return SimpleNamespace(
        id=f"{day.isoformat()}-{merchant}-{amount}",
        transaction_date=day,
        amount=amount,
        transaction_type=kind,
        category=category,
        merchant=merchant,
        description=description or merchant,
        is_refund=False,
        is_cashback=False,
        is_duplicate=False,
        is_subscription=False,
        is_anomaly=False,
        is_small_spend=False,
        needs_review=False,
        need_want_waste_type="unknown",
        category_confidence=0.9,
    )


def sample_transactions():
    """Return transactions covering recurring bills, refunds, and two month comparison."""
    return [
        tx(date(2026, 6, 1), 45000, "credit", "Income", "Salary"),
        tx(date(2026, 6, 2), -7500, "debit", "Rent & Housing", "Rent"),
        tx(date(2026, 6, 5), -499, "debit", "Subscriptions", "Netflix"),
        tx(date(2026, 6, 7), -1200, "debit", "Food & Dining", "Zomato"),
        tx(date(2026, 6, 9), -799, "debit", "Shopping", "Amazon Failed", "Failed order Amazon"),
        tx(date(2026, 7, 1), 45000, "credit", "Income", "Salary"),
        tx(date(2026, 7, 2), -7500, "debit", "Rent & Housing", "Rent"),
        tx(date(2026, 7, 5), -499, "debit", "Subscriptions", "Netflix"),
        tx(date(2026, 7, 7), -5200, "debit", "Food & Dining", "Zomato"),
        tx(date(2026, 7, 10), 799, "credit", "Refund/Cashback", "Amazon Refund", "Refund for failed order Amazon"),
    ]


def test_bill_reminders_detect_recurring_fixed_payments():
    """Bill reminders should predict fixed recurring payments from statement history."""
    result = detect_bill_reminders(sample_transactions())
    reminders = result["data"]["reminders"]
    merchants = {row["merchant"] for row in reminders}
    assert "Rent" in merchants
    assert result["data"]["summary"]["total_reminders"] >= 1


def test_refund_tracking_detects_received_refund():
    """Refund tracking should expose refund credits and review rows."""
    result = detect_refund_reversal_tracking(sample_transactions())
    data = result["data"]
    assert data["summary"]["refunds_received_count"] == 1
    assert data["summary"]["refunds_received_amount"] == 799


def test_month_change_explanation_returns_drivers():
    """Month-change explanation should explain latest month movement."""
    result = explain_latest_month_change(sample_transactions())
    data = result["data"]
    assert data["from_month"] == "2026-06"
    assert data["to_month"] == "2026-07"
    assert data["drivers"]
    assert data["category_drivers"]


def test_smart_alerts_combines_bill_and_refund_data():
    """Combined smart alerts should include reminder and refund summaries."""
    result = detect_smart_alerts(sample_transactions())
    data = result["data"]
    assert "bill_reminders" in data
    assert "refund_tracking" in data
    assert data["summary"]["action_required_count"] >= 0
