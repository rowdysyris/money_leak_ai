"""Synthetic category model trainer for MoneyLeak AI optional ML fallback."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

try:
    from ml.features import combine_text, extract_feature_matrix, set_vectorizer_for_process
except ModuleNotFoundError:  # Support direct execution: python ml/train_category_model.py
    from features import combine_text, extract_feature_matrix, set_vectorizer_for_process

logger = logging.getLogger("moneyleak-ai.ml.train_category_model")
MODEL_DIR = Path(__file__).resolve().parent / "models"
CATEGORIES = [
    "Food & Dining",
    "Groceries",
    "Shopping",
    "Subscriptions",
    "Entertainment",
    "Travel & Transport",
    "Rent & Housing",
    "Bills & Utilities",
    "Education",
    "Health & Medical",
    "Personal Care",
    "EMI & Loans",
    "Investments & Savings",
    "Bank Charges & Fees",
    "Transfers",
    "Cash Withdrawal",
    "Miscellaneous",
]

CATEGORY_SEEDS: dict[str, list[tuple[str, str, float]]] = {
    "Food & Dining": [("Swiggy", "SWIGGY food order", 420), ("Zomato", "ZOMATO food delivery", 350), ("Dominos", "Pizza dinner", 599), ("FreshMenu", "Meal delivery order", 280)],
    "Groceries": [("Blinkit", "BLINKIT grocery order", 850), ("Zepto", "Vegetables and groceries", 640), ("BigBasket", "Monthly grocery basket", 2100), ("DMart", "Supermarket purchase", 1750)],
    "Shopping": [("Amazon", "AMAZON shopping order", 1499), ("Flipkart", "Electronics purchase", 2399), ("Myntra", "Fashion shopping", 1899), ("Croma", "Gadget accessory", 1299)],
    "Subscriptions": [("Netflix", "NETFLIX monthly subscription", 649), ("Spotify", "Spotify premium", 119), ("Google One", "Cloud storage subscription", 130), ("ChatGPT", "OPENAI monthly plan", 1999)],
    "Entertainment": [("BookMyShow", "Movie tickets", 780), ("PVR", "Cinema snacks and ticket", 950), ("INOX", "Weekend movie", 700), ("Cinepolis", "Film booking", 620)],
    "Travel & Transport": [("Uber", "Cab ride", 310), ("Ola", "Taxi payment", 285), ("IRCTC", "Train ticket", 1280), ("Indigo", "Flight booking", 5200)],
    "Rent & Housing": [("NoBroker", "Rent payment", 15000), ("Nestaway", "Monthly house rent", 12000), ("Magicbricks", "Housing service", 999), ("Landlord", "Flat rent transfer", 10000)],
    "Bills & Utilities": [("Airtel", "Mobile recharge", 399), ("Jio", "Jio fiber bill", 999), ("BESCOM", "Electricity bill", 1650), ("Adani Gas", "Gas bill", 890)],
    "Education": [("Udemy", "Online course", 499), ("Coursera", "Certificate subscription", 3900), ("Unacademy", "Exam preparation", 2500), ("Aakash", "Coaching fee", 15000)],
    "Health & Medical": [("Apollo Pharmacy", "Medicine purchase", 540), ("1mg", "Lab test and medicine", 760), ("Clinic", "Doctor consultation", 700), ("Pharmeasy", "Healthcare order", 690)],
    "Personal Care": [("Lakme Salon", "Salon grooming", 1200), ("Mamaearth", "Personal care products", 650), ("Cult.fit", "Fitness class", 999), ("Jawed Habib", "Haircut salon", 450)],
    "EMI & Loans": [("HDFC Loan", "EMI debit", 4500), ("Bajaj Finance", "Loan repayment", 3200), ("KreditBee", "Lend repay", 2800), ("SBI EMI", "Monthly loan emi", 6100)],
    "Investments & Savings": [("Zerodha", "Investment transfer", 5000), ("Groww", "Mutual fund SIP", 3000), ("Paytm Money", "SIP investment", 2000), ("HDFC Securities", "Equity investment", 7000)],
    "Bank Charges & Fees": [("Bank", "ATM charges", 25), ("Bank", "Annual fee GST charge", 590), ("Bank", "Processing fee", 350), ("Bank", "Penalty service charge", 450)],
    "Transfers": [("Rahul", "UPI transfer to Rahul", 1000), ("9034567890", "Paid to friend", 500), ("P2A", "Sent to savings account", 2500), ("Family", "Transfer to family", 3000)],
    "Cash Withdrawal": [("ATM", "ATM cash withdrawal", 2000), ("ATM", "Cash withdrawal from ATM", 5000), ("Bank ATM", "ATM withdrawal", 1000), ("SBI ATM", "Cash withdraw", 3000)],
    "Miscellaneous": [("Unknown", "Misc payment", 220), ("Local Vendor", "UPI payment", 180), ("Service", "Other transaction", 450), ("Merchant", "General expense", 300)],
}


def generate_synthetic_training_data(sample_count: int = 500) -> list[dict[str, Any]]:
    """Generate realistic synthetic transaction samples across all supported categories."""
    samples: list[dict[str, Any]] = []
    per_category = max(1, sample_count // len(CATEGORIES))
    for category in CATEGORIES:
        seeds = CATEGORY_SEEDS.get(category, [])
        for index in range(per_category):
            merchant, description, amount = seeds[index % len(seeds)] if seeds else ("Unknown", "Generic transaction", 100.0)
            variation = 1.0 + ((index % 7) - 3) * 0.04
            samples.append(
                {
                    "merchant": merchant,
                    "description": f"{description} ref {index}",
                    "amount": round(float(amount) * variation, 2),
                    "transaction_date": f"2024-01-{(index % 28) + 1:02d}",
                    "is_refund": "refund" in description.lower(),
                    "is_late_night": index % 11 == 0,
                    "category": category,
                }
            )
    while len(samples) < sample_count:
        category = CATEGORIES[len(samples) % len(CATEGORIES)]
        merchant, description, amount = CATEGORY_SEEDS[category][len(samples) % len(CATEGORY_SEEDS[category])]
        samples.append(
            {
                "merchant": merchant,
                "description": f"{description} extra {len(samples)}",
                "amount": float(amount),
                "transaction_date": f"2024-02-{(len(samples) % 28) + 1:02d}",
                "is_refund": False,
                "is_late_night": False,
                "category": category,
            }
        )
    return samples[:sample_count]


def train_category_model(output_dir: str | Path | None = None, sample_count: int = 500) -> dict[str, Any]:
    """Train and save an XGBoost category classifier using synthetic transaction data."""
    target_dir = Path(output_dir) if output_dir is not None else MODEL_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    samples = generate_synthetic_training_data(sample_count)
    if len(samples) < 200:
        logger.warning("Training data is small; category model accuracy may be limited")

    texts = [combine_text(sample) for sample in samples]
    vectorizer = TfidfVectorizer(max_features=500, ngram_range=(1, 2))
    vectorizer.fit(texts)
    set_vectorizer_for_process(vectorizer)
    features = extract_feature_matrix(samples, vectorizer=vectorizer)
    labels = [str(sample.get("category") or "Miscellaneous") for sample in samples]
    label_encoder = LabelEncoder()
    encoded_labels = label_encoder.fit_transform(labels)

    stratify = encoded_labels if len(set(encoded_labels)) > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        features,
        encoded_labels,
        test_size=0.2,
        random_state=42,
        stratify=stratify,
    )
    model = XGBClassifier(
        n_estimators=80,
        max_depth=4,
        learning_rate=0.12,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=1,
    )
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    accuracy = float(accuracy_score(y_test, predictions)) if len(y_test) > 0 else 0.0

    bundle = {"model": model, "label_encoder": label_encoder, "vectorizer": vectorizer, "categories": list(label_encoder.classes_)}
    category_path = target_dir / "category_model.pkl"
    vectorizer_path = target_dir / "tfidf_vectorizer.pkl"
    with category_path.open("wb") as category_file:
        pickle.dump(bundle, category_file)
    with vectorizer_path.open("wb") as vectorizer_file:
        pickle.dump(vectorizer, vectorizer_file)

    logger.info("Category model trained", extra={"accuracy": round(accuracy, 3), "sample_count": len(samples)})
    return {"accuracy": accuracy, "sample_count": len(samples), "model_path": str(category_path), "vectorizer_path": str(vectorizer_path)}


def main() -> None:
    """Train the category model when this module is executed as a script."""
    train_category_model()


if __name__ == "__main__":
    main()
