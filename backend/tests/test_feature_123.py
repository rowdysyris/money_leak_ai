"""Tests for multi-month analysis, financial health score, and goal planner features."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from services.financial_health import calculate_health_score
from services.goal_planner import build_goal_plan
from services.monthly_analysis import calculate_monthly_analysis, calculate_monthly_comparison


def tx(day: date, amount: float, kind: str, category: str, merchant: str = "Merchant"):
    """Build a lightweight transaction object for service tests."""
    return SimpleNamespace(
        id=f"{day.isoformat()}-{merchant}-{amount}",
        transaction_date=day,
        amount=amount,
        transaction_type=kind,
        category=category,
        merchant=merchant,
        description=merchant,
        is_refund=False,
        is_cashback=False,
        is_anomaly=False,
        needs_review=False,
        need_want_waste_type="unknown",
    )


def sample_transactions():
    """Return multi-month sample transactions."""
    return [
        tx(date(2026, 6, 5), 45000, "credit", "Income", "Salary"),
        tx(date(2026, 6, 6), -10000, "debit", "Rent & Housing", "Rent"),
        tx(date(2026, 6, 7), -2000, "debit", "Shopping", "Shopping"),
        tx(date(2026, 6, 8), -5000, "debit", "Investments & Savings", "SIP"),
        tx(date(2026, 7, 5), 45000, "credit", "Income", "Salary"),
        tx(date(2026, 7, 6), -9000, "debit", "Rent & Housing", "Rent"),
        tx(date(2026, 7, 7), -1200, "debit", "Shopping", "Shopping"),
        tx(date(2026, 7, 8), -7000, "debit", "Investments & Savings", "SIP"),
    ]


def test_monthly_analysis_returns_month_rows():
    """Monthly analysis should return one row per calendar month."""
    result = calculate_monthly_analysis(sample_transactions())
    months = result["data"]["months"]
    assert len(months) == 2
    assert months[0]["month"] == "2026-06"
    assert months[1]["month"] == "2026-07"
    assert months[1]["actionable_spend"] < months[0]["actionable_spend"]


def test_monthly_comparison_returns_spend_change():
    """Monthly comparison should calculate spending change between adjacent months."""
    result = calculate_monthly_comparison(sample_transactions())
    comparison = result["data"]["comparisons"][0]
    assert comparison["from_month"] == "2026-06"
    assert comparison["to_month"] == "2026-07"
    assert comparison["spending_change"] < 0


def test_financial_health_score_has_income_ratios():
    """Financial health score should expose income-aware ratios."""
    result = calculate_health_score(sample_transactions())
    data = result["data"]
    assert 0 <= data["score"] <= 100
    assert data["income_total"] == 90000
    assert data["savings_rate_pct"] > 0
    assert data["debt_pressure_pct"] == 0


def test_goal_planner_returns_required_monthly_saving():
    """Goal planner should calculate required monthly saving and actions."""
    result = build_goal_plan(sample_transactions(), "Emergency fund", 60000, 6)
    data = result["data"]
    assert data["required_monthly_saving"] == 10000
    assert data["goal_name"] == "Emergency fund"
    assert isinstance(data["actions"], list)
