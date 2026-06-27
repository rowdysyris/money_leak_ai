"""Recurring payment and subscription detection service."""

from __future__ import annotations

from datetime import timedelta
from statistics import median
from typing import Any

from services.analytics_utils import (
    debit_amount,
    display_merchant_name,
    empty_result,
    get_category,
    get_field,
    is_high_value_or_anomaly,
    is_refund,
    normalize_merchant_name,
    parse_date,
    service_result,
    valid_transactions,
)

EXPECTED_MONTHLY_SUBSCRIPTIONS = {
    "canva",
    "netflix",
    "spotify",
    "google one",
    "icloud",
    "chatgpt",
    "openai",
    "adobe",
    "microsoft 365",
    "prime video",
    "hotstar",
}

KNOWN_SUBSCRIPTION_KEYWORDS = {
    "netflix",
    "spotify",
    "prime video",
    "hotstar",
    "disney",
    "zee5",
    "sonyliv",
    "jiocinema",
    "youtube premium",
    "canva",
    "adobe",
    "microsoft 365",
    "google one",
    "icloud",
    "dropbox",
    "notion",
    "slack",
    "zoom",
    "github",
    "chatgpt",
    "openai",
    "anthropic",
    "linkedin premium",
}


def frequency_from_interval(interval_days: float) -> str | None:
    """Classify a median interval into a recurring frequency label."""
    if 6 <= interval_days <= 8:
        return "weekly"
    if 13 <= interval_days <= 16:
        return "biweekly"
    if 28 <= interval_days <= 32:
        return "monthly"
    if 85 <= interval_days <= 95:
        return "quarterly"
    if 360 <= interval_days <= 370:
        return "yearly"
    return None


def monthly_cost_for_frequency(average_amount: float, frequency: str) -> float:
    """Convert average recurring charge into estimated monthly cost."""
    if frequency == "weekly":
        return average_amount * 4.33
    if frequency == "biweekly":
        return average_amount * 2.17
    if frequency == "monthly":
        return average_amount
    if frequency == "quarterly":
        return average_amount / 3.0
    if frequency == "yearly":
        return average_amount / 12.0
    return average_amount


def cancellation_priority(yearly_cost: float) -> str:
    """Return a cancellation priority from annual cost using practical Indian-user thresholds."""
    if yearly_cost >= 6000:
        return "high"
    if yearly_cost >= 1500:
        return "medium"
    return "low"


def merchant_is_known_subscription(merchant_normalized: str) -> bool:
    """Return True when a merchant name is a known subscription provider."""
    if not merchant_normalized:
        return False
    return any(keyword in merchant_normalized for keyword in KNOWN_SUBSCRIPTION_KEYWORDS)


def expected_monthly_subscription(merchant_normalized: str) -> bool:
    """Return True when a known merchant normally bills monthly in this app domain."""
    return any(keyword in merchant_normalized for keyword in EXPECTED_MONTHLY_SUBSCRIPTIONS)


def is_subscription_candidate(transaction: Any) -> bool:
    """Return True when a transaction is eligible for subscription detection."""
    amount = debit_amount(transaction)
    if amount <= 0:
        return False
    if is_refund(transaction):
        return False
    if is_high_value_or_anomaly(transaction):
        return False
    if bool(get_field(transaction, "is_duplicate", False)):
        return False
    category = get_category(transaction)
    if category in {"Transfers", "Cash Withdrawal", "Investments & Savings", "Bank Charges & Fees"}:
        return False
    return parse_date(get_field(transaction, "transaction_date")) is not None


def amount_within_tolerance(amount: float, reference_amount: float, tolerance: float = 0.15) -> bool:
    """Return True when amount is inside the accepted percentage tolerance."""
    if reference_amount <= 0:
        return False
    return abs(amount - reference_amount) / reference_amount <= tolerance


def cluster_transactions_by_amount(transactions: list[Any]) -> list[list[Any]]:
    """Group merchant transactions into stable amount clusters using ±15% tolerance."""
    sorted_transactions = sorted(transactions, key=lambda transaction: debit_amount(transaction))
    clusters: list[list[Any]] = []
    for transaction in sorted_transactions:
        amount = debit_amount(transaction)
        if amount <= 0:
            continue
        placed = False
        for cluster in clusters:
            cluster_amounts = [debit_amount(item) for item in cluster if debit_amount(item) > 0]
            reference_amount = float(median(cluster_amounts)) if cluster_amounts else 0.0
            if amount_within_tolerance(amount, reference_amount):
                cluster.append(transaction)
                placed = True
                break
        if not placed:
            clusters.append([transaction])
    return [cluster for cluster in clusters if len(cluster) >= 2]


def median_interval_for_transactions(transactions: list[Any]) -> float | None:
    """Return the median interval in days for dated transactions."""
    dated_transactions = sorted(
        [transaction for transaction in transactions if parse_date(get_field(transaction, "transaction_date"))],
        key=lambda transaction: parse_date(get_field(transaction, "transaction_date")),
    )
    dates = [parse_date(get_field(transaction, "transaction_date")) for transaction in dated_transactions]
    intervals = [(dates[index] - dates[index - 1]).days for index in range(1, len(dates)) if dates[index] and dates[index - 1]]
    positive_intervals = [interval for interval in intervals if interval > 0]
    return float(median(positive_intervals)) if positive_intervals else None


def interval_consistency_score(transactions: list[Any], median_interval: float | None) -> float:
    """Return a 0-1 score measuring interval stability inside a cluster."""
    if median_interval is None or median_interval <= 0:
        return 0.0
    dated_transactions = sorted(
        [transaction for transaction in transactions if parse_date(get_field(transaction, "transaction_date"))],
        key=lambda transaction: parse_date(get_field(transaction, "transaction_date")),
    )
    dates = [parse_date(get_field(transaction, "transaction_date")) for transaction in dated_transactions]
    intervals = [(dates[index] - dates[index - 1]).days for index in range(1, len(dates)) if dates[index] and dates[index - 1]]
    intervals = [interval for interval in intervals if interval > 0]
    if not intervals:
        return 0.0
    tolerance = max(2.0, median_interval * 0.20)
    stable = sum(1 for interval in intervals if abs(interval - median_interval) <= tolerance)
    return stable / len(intervals)


def extract_monthly_chain(transactions: list[Any]) -> list[Any]:
    """Return the longest monthly-like dated chain from an amount-consistent cluster."""
    dated = sorted(
        [transaction for transaction in transactions if parse_date(get_field(transaction, "transaction_date"))],
        key=lambda transaction: parse_date(get_field(transaction, "transaction_date")),
    )
    if len(dated) < 2:
        return []
    best_chain: list[Any] = []
    for start_index, start_transaction in enumerate(dated):
        chain = [start_transaction]
        last_date = parse_date(get_field(start_transaction, "transaction_date"))
        for candidate in dated[start_index + 1 :]:
            candidate_date = parse_date(get_field(candidate, "transaction_date"))
            if last_date is None or candidate_date is None:
                continue
            interval = (candidate_date - last_date).days
            if 26 <= interval <= 35:
                chain.append(candidate)
                last_date = candidate_date
            elif interval < 26:
                continue
        if len(chain) > len(best_chain):
            best_chain = chain
    return best_chain


def recurring_cluster_score(transactions: list[Any], known_subscription: bool, monthly_expected: bool) -> tuple[int, float, str | None]:
    """Score an amount-consistent cluster for subscription likelihood."""
    occurrence_count = len(transactions)
    median_interval = median_interval_for_transactions(transactions)
    frequency = frequency_from_interval(median_interval) if median_interval is not None else None
    consistency = interval_consistency_score(transactions, median_interval)
    required_consistency = 0.60 if monthly_expected and frequency == "monthly" else 0.75
    if frequency and consistency >= required_consistency:
        if frequency in {"weekly", "biweekly"} and occurrence_count < 3:
            frequency = None
        if monthly_expected and frequency not in {"monthly", "yearly"}:
            frequency = None
        if frequency:
            return 4 if occurrence_count >= 3 else 3, float(median_interval or 0.0), frequency
    if known_subscription and occurrence_count >= 2:
        return 2, float(median_interval or 0.0), "irregular"
    return 0, float(median_interval or 0.0), None


def select_best_recurring_cluster(transactions: list[Any], known_subscription: bool, monthly_expected: bool = False) -> tuple[list[Any], float | None, str] | None:
    """Select the best stable amount cluster for one merchant."""
    best_cluster: list[Any] | None = None
    best_frequency: str | None = None
    best_interval: float | None = None
    best_rank = -1
    best_count = -1
    for cluster in cluster_transactions_by_amount(transactions):
        scored_cluster = cluster
        if monthly_expected:
            monthly_chain = extract_monthly_chain(cluster)
            if len(monthly_chain) >= 2:
                scored_cluster = monthly_chain
        rank, median_interval, frequency = recurring_cluster_score(scored_cluster, known_subscription, monthly_expected)
        if not frequency:
            continue
        cluster_count = len(scored_cluster)
        if rank > best_rank or (rank == best_rank and cluster_count > best_count):
            best_cluster = scored_cluster
            best_frequency = frequency
            best_interval = median_interval if median_interval > 0 else None
            best_rank = rank
            best_count = cluster_count
    if not best_cluster or not best_frequency:
        return None
    return best_cluster, best_interval, best_frequency


def subscription_confidence(frequency: str, occurrence_count: int, known_subscription: bool) -> float:
    """Return a conservative confidence score for a subscription detection."""
    if frequency == "irregular":
        return 0.62 if known_subscription else 0.45
    base_score = 0.78
    if occurrence_count >= 3:
        base_score += 0.1
    if known_subscription:
        base_score += 0.07
    return round(min(0.98, base_score), 2)


def build_subscription_record(merchant: str, merchant_transactions: list[Any], frequency: str, median_interval: float | None, known_subscription: bool) -> dict[str, Any]:
    """Build one detected subscription record from a consistent recurring amount cluster."""
    amounts = [debit_amount(transaction) for transaction in merchant_transactions if debit_amount(transaction) > 0]
    dates = [parsed for parsed in (parse_date(get_field(transaction, "transaction_date")) for transaction in merchant_transactions) if parsed]
    average_amount = round(sum(amounts) / len(amounts), 2) if amounts else 0.0
    monthly_cost = round(monthly_cost_for_frequency(average_amount, frequency), 2)
    yearly_cost = round(monthly_cost * 12.0, 2)
    last_charge_date = max(dates) if dates else None
    next_predicted_date = None
    if frequency != "irregular" and last_charge_date and median_interval and median_interval > 0:
        next_predicted_date = last_charge_date + timedelta(days=int(round(median_interval)))
    return {
        "merchant": merchant,
        "frequency": frequency,
        "average_amount": average_amount,
        "monthly_cost": monthly_cost,
        "yearly_cost": yearly_cost,
        "last_charge_date": last_charge_date.isoformat() if last_charge_date else None,
        "next_predicted_date": next_predicted_date.isoformat() if next_predicted_date else None,
        "cancellation_priority": cancellation_priority(yearly_cost),
        "occurrence_count": len(merchant_transactions),
        "median_interval_days": round(float(median_interval or 0.0), 2),
        "confidence_score": subscription_confidence(frequency, len(merchant_transactions), known_subscription),
    }


def detect_subscriptions(transactions: list[Any]) -> dict[str, Any]:
    """Detect recurring payments while avoiding anomaly-driven and duplicate-driven overcounting."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result([])

    grouped: dict[str, list[Any]] = {}
    display_names: dict[str, str] = {}
    for transaction in safe_transactions:
        if not is_subscription_candidate(transaction):
            continue
        merchant = display_merchant_name(get_field(transaction, "merchant", None))
        normalized = normalize_merchant_name(merchant)
        if not normalized:
            continue
        looks_like_subscription = merchant_is_known_subscription(normalized) or get_category(transaction) == "Subscriptions"
        if not looks_like_subscription:
            continue
        grouped.setdefault(normalized, []).append(transaction)
        display_names.setdefault(normalized, merchant)

    subscriptions: list[dict[str, Any]] = []
    for normalized, merchant_transactions in grouped.items():
        if len(merchant_transactions) < 2:
            continue
        known_subscription = merchant_is_known_subscription(normalized) or get_category(merchant_transactions[0]) == "Subscriptions"
        selected_cluster = select_best_recurring_cluster(merchant_transactions, known_subscription, expected_monthly_subscription(normalized))
        if not selected_cluster:
            continue
        recurring_transactions, median_interval, frequency = selected_cluster
        subscriptions.append(
            build_subscription_record(
                display_names.get(normalized, normalized.title()),
                recurring_transactions,
                frequency,
                median_interval,
                known_subscription,
            )
        )

    subscriptions.sort(key=lambda value: float(value.get("yearly_cost") or 0.0), reverse=True)
    return service_result(subscriptions, [] if subscriptions else ["No subscriptions detected"])
