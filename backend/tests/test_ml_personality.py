"""Deterministic spending-personality classification tests."""

from services.report_summary import classify_personality


def transaction(category: str, amount: float = -100.0, **extra) -> dict:
    return {
        "category": category,
        "amount": amount,
        "transaction_type": "debit",
        "transaction_date": "2024-01-01",
        "is_anomaly": False,
        **extra,
    }


def breakdown(category: str, total: float, kind: str = "want") -> dict:
    return {"category": category, "total_amount": total, "need_want_waste_type": kind}


def test_empty_personality_is_balanced() -> None:
    data = classify_personality([], [])["data"]
    assert data["personality_type"] == "Balanced Spender"
    assert data["description"]
    assert data["confidence"] == 0.0


def test_dominant_food_shopping_and_transfer_personalities() -> None:
    food = classify_personality([transaction("Food & Dining")], [breakdown("Food & Dining", 900)])["data"]
    shopping = classify_personality([transaction("Shopping")], [breakdown("Shopping", 900)])["data"]
    transfers = classify_personality([transaction("Transfers") for _ in range(5)], [breakdown("Transfers", 500, "unknown")])["data"]
    assert food["personality_type"] == "Food Spender"
    assert shopping["personality_type"] == "Shopping Spender"
    assert transfers["personality_type"] == "Transfer-Heavy"


def test_subscription_and_late_night_personalities() -> None:
    subscriptions = [transaction("Subscriptions") for _ in range(5)]
    result = classify_personality(subscriptions, [breakdown("Subscriptions", 500)])["data"]
    assert result["personality_type"] == "Subscription Leaker"
    late = [transaction("Miscellaneous", is_late_night=True) for _ in range(5)]
    late_result = classify_personality(late, [breakdown("Miscellaneous", 500, "unknown")])["data"]
    assert late_result["personality_type"] == "Late-Night Spender"
