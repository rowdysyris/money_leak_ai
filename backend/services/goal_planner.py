"""Goal-based savings planner service."""

from __future__ import annotations

from typing import Any

from services.analytics_utils import estimate_income, service_result, total_credit_received, valid_transactions
from services.duplicate_detector import detect_duplicates
from services.report_summary import generate_saving_priority
from services.subscription_detector import detect_subscriptions


def build_goal_plan(transactions: list[Any], goal_name: str, target_amount: float, months: int) -> dict[str, Any]:
    """Return a deterministic savings plan for a user goal."""
    safe_months = max(1, int(months or 1))
    safe_target = max(0.0, float(target_amount or 0.0))
    safe_transactions = valid_transactions(transactions)
    subscriptions = detect_subscriptions(safe_transactions).get("data", [])
    duplicates = detect_duplicates(safe_transactions).get("data", [])
    priorities = generate_saving_priority(safe_transactions, subscriptions, duplicates).get("data", [])
    required_monthly = round(safe_target / safe_months, 2) if safe_months > 0 else safe_target
    possible_monthly = round(sum(float(item.get("possible_monthly_saving", 0.0) or 0.0) for item in priorities), 2)
    covered_amount = round(min(possible_monthly, required_monthly), 2)
    remaining_gap = round(max(0.0, required_monthly - possible_monthly), 2)
    income_total = total_credit_received(safe_transactions)
    income_baseline = estimate_income(safe_transactions)

    actions = []
    for item in priorities[:5]:
        actions.append(
            {
                "title": item.get("title") or item.get("target") or "Saving action",
                "monthly_saving": round(float(item.get("possible_monthly_saving", 0.0) or 0.0), 2),
                "action": item.get("action") or "Review this spend category.",
                "difficulty": item.get("difficulty", "medium"),
            }
        )
    if remaining_gap > 0:
        actions.append(
            {
                "title": "Additional monthly saving needed",
                "monthly_saving": remaining_gap,
                "action": "Increase savings target, extend timeline, or reduce discretionary spending further.",
                "difficulty": "medium",
            }
        )

    feasibility = "On Track" if possible_monthly >= required_monthly else "Gap Remaining" if possible_monthly > 0 else "Needs Manual Plan"
    data = {
        "goal_name": goal_name.strip() or "Savings goal",
        "target_amount": round(safe_target, 2),
        "months": safe_months,
        "required_monthly_saving": required_monthly,
        "possible_monthly_saving": possible_monthly,
        "covered_by_recommendations": covered_amount,
        "remaining_monthly_gap": remaining_gap,
        "feasibility": feasibility,
        "income_total": round(income_total, 2),
        "monthly_income_baseline": round(income_baseline, 2),
        "actions": actions,
    }
    warnings = []
    if not safe_transactions:
        warnings.append("No transactions found; goal plan uses only manual target values.")
    if safe_target <= 0:
        warnings.append("Enter a target amount greater than zero for a useful plan.")
    return service_result(data, warnings)
