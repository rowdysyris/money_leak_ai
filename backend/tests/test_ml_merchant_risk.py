"""Merchant repeat-spend risk tests."""

from services.merchant_risk import calculate_merchant_risk, top_merchant_risks


def rows(merchant: str, count: int, amount: float = -100.0) -> list[dict]:
    return [{"merchant": merchant, "amount": amount, "transaction_type": "debit"} for _ in range(count)]


def test_merchant_risk_contract_and_thresholds() -> None:
    low = calculate_merchant_risk("Cafe", rows("Cafe", 1))
    high = calculate_merchant_risk("Cafe", rows("Cafe", 50))
    assert low["risk_level"] == "low"
    assert high["risk_level"] == "high"
    assert 0 <= high["addiction_score"] <= 1
    assert high["controllability"] in {"easy", "moderate", "difficult"}
    assert high["transaction_count"] == 50
    assert high["insight"]


def test_top_merchant_risks_is_capped_and_empty_safe() -> None:
    transactions = []
    for index in range(8):
        transactions.extend(rows(f"Merchant {index}", index + 1))
    assert calculate_merchant_risk("Unknown", [])["transaction_count"] == 0
    result = top_merchant_risks(transactions)
    assert len(result) == 5
    assert result[0]["addiction_score"] >= result[-1]["addiction_score"]
