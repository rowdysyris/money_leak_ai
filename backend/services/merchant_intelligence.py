"""Deterministic merchant intelligence rules for MoneyLeak AI categorization."""

from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz, process

ALLOWED_CATEGORIES: tuple[str, ...] = (
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
    "Income",
    "Refund/Cashback",
    "Loan Credit",
    "Investment Withdrawal",
    "Credit",
    "Miscellaneous",
)

CATEGORY_NEED_WANT_WASTE: dict[str, str] = {
    "Food & Dining": "want",
    "Groceries": "need",
    "Shopping": "want",
    "Subscriptions": "want",
    "Entertainment": "want",
    "Travel & Transport": "want",
    "Rent & Housing": "need",
    "Bills & Utilities": "need",
    "Education": "need",
    "Health & Medical": "need",
    "Personal Care": "want",
    "EMI & Loans": "need",
    "Investments & Savings": "savings",
    "Bank Charges & Fees": "waste",
    "Transfers": "unknown",
    "Cash Withdrawal": "unknown",
    "Income": "unknown",
    "Refund/Cashback": "unknown",
    "Loan Credit": "unknown",
    "Investment Withdrawal": "savings",
    "Credit": "unknown",
    "Miscellaneous": "unknown",
}

VERIFIED_MERCHANTS: dict[str, str] = {
    "swiggy": "Food & Dining",
    "zomato": "Food & Dining",
    "dominos": "Food & Dining",
    "mcdonald": "Food & Dining",
    "burger king": "Food & Dining",
    "kfc": "Food & Dining",
    "pizza hut": "Food & Dining",
    "subway": "Food & Dining",
    "dunkin": "Food & Dining",
    "starbucks": "Food & Dining",
    "cafe coffee day": "Food & Dining",
    "ccd": "Food & Dining",
    "haldirams": "Food & Dining",
    "bikanervala": "Food & Dining",
    "box8": "Food & Dining",
    "faasos": "Food & Dining",
    "behrouz": "Food & Dining",
    "oven story": "Food & Dining",
    "rebel foods": "Food & Dining",
    "fassos": "Food & Dining",
    "eat fit": "Food & Dining",
    "freshmenu": "Food & Dining",
    "biryani by kilo": "Food & Dining",
    "paradise biryani": "Food & Dining",
    "barbeque nation": "Food & Dining",
    "punjab grill": "Food & Dining",
    "blinkit": "Groceries",
    "zepto": "Groceries",
    "bigbasket": "Groceries",
    "grofers": "Groceries",
    "jiomart": "Groceries",
    "dmart": "Groceries",
    "reliance fresh": "Groceries",
    "more supermarket": "Groceries",
    "star bazaar": "Groceries",
    "nilgiris": "Groceries",
    "nature basket": "Groceries",
    "spencers": "Groceries",
    "licious": "Groceries",
    "milkbasket": "Groceries",
    "country delight": "Groceries",
    "amazon": "Shopping",
    "flipkart": "Shopping",
    "myntra": "Shopping",
    "ajio": "Shopping",
    "nykaa": "Shopping",
    "meesho": "Shopping",
    "snapdeal": "Shopping",
    "tatacliq": "Shopping",
    "lifestyle": "Shopping",
    "shoppers stop": "Shopping",
    "westside": "Shopping",
    "pantaloons": "Shopping",
    "max fashion": "Shopping",
    "zara": "Shopping",
    "h m": "Shopping",
    "uniqlo": "Shopping",
    "ikea": "Shopping",
    "croma": "Shopping",
    "vijay sales": "Shopping",
    "reliance digital": "Shopping",
    "apple store": "Shopping",
    "netflix": "Subscriptions",
    "spotify": "Subscriptions",
    "prime video": "Subscriptions",
    "hotstar": "Subscriptions",
    "disney": "Subscriptions",
    "zee5": "Subscriptions",
    "sonyliv": "Subscriptions",
    "jiocinema": "Subscriptions",
    "youtube premium": "Subscriptions",
    "canva": "Subscriptions",
    "adobe": "Subscriptions",
    "microsoft 365": "Subscriptions",
    "google one": "Subscriptions",
    "icloud": "Subscriptions",
    "dropbox": "Subscriptions",
    "notion": "Subscriptions",
    "slack": "Subscriptions",
    "zoom": "Subscriptions",
    "github": "Subscriptions",
    "chatgpt": "Subscriptions",
    "openai": "Subscriptions",
    "anthropic": "Subscriptions",
    "linkedin premium": "Subscriptions",
    "bookmyshow": "Entertainment",
    "paytm movies": "Entertainment",
    "pvr": "Entertainment",
    "inox": "Entertainment",
    "cinepolis": "Entertainment",
    "igp": "Entertainment",
    "zomato events": "Entertainment",
    "uber": "Travel & Transport",
    "ola": "Travel & Transport",
    "rapido": "Travel & Transport",
    "meru": "Travel & Transport",
    "yulu": "Travel & Transport",
    "bounce": "Travel & Transport",
    "namma yatri": "Travel & Transport",
    "redbus": "Travel & Transport",
    "irctc": "Travel & Transport",
    "makemytrip": "Travel & Transport",
    "goibibo": "Travel & Transport",
    "cleartrip": "Travel & Transport",
    "easemytrip": "Travel & Transport",
    "indigo": "Travel & Transport",
    "air india": "Travel & Transport",
    "vistara": "Travel & Transport",
    "spicejet": "Travel & Transport",
    "akasa": "Travel & Transport",
    "mmthotel": "Travel & Transport",
    "oyo": "Travel & Transport",
    "treebo": "Travel & Transport",
    "fabhotels": "Travel & Transport",
    "zostel": "Travel & Transport",
    "airbnb": "Travel & Transport",
    "magicbricks": "Rent & Housing",
    "99acres": "Rent & Housing",
    "nestaway": "Rent & Housing",
    "nobroker": "Rent & Housing",
    "commonfloor": "Rent & Housing",
    "rent": "Rent & Housing",
    "landlord": "Rent & Housing",
    "rent landlord": "Rent & Housing",
    "rent transfer landlord": "Rent & Housing",
    "lease": "Rent & Housing",
    "flat rent": "Rent & Housing",
    "airtel": "Bills & Utilities",
    "jio": "Bills & Utilities",
    "vi": "Bills & Utilities",
    "bsnl": "Bills & Utilities",
    "idea": "Bills & Utilities",
    "vodafone": "Bills & Utilities",
    "tata sky": "Bills & Utilities",
    "dish tv": "Bills & Utilities",
    "d2h": "Bills & Utilities",
    "sun direct": "Bills & Utilities",
    "bescom": "Bills & Utilities",
    "msedcl": "Bills & Utilities",
    "bses": "Bills & Utilities",
    "cesc": "Bills & Utilities",
    "tata power": "Bills & Utilities",
    "adani gas": "Bills & Utilities",
    "mahanagar gas": "Bills & Utilities",
    "indraprastha gas": "Bills & Utilities",
    "paytm postpaid": "Bills & Utilities",
    "jio fiber": "Bills & Utilities",
    "act fibernet": "Bills & Utilities",
    "coursera": "Education",
    "udemy": "Education",
    "unacademy": "Education",
    "byju": "Education",
    "vedantu": "Education",
    "upgrad": "Education",
    "great learning": "Education",
    "simplilearn": "Education",
    "edureka": "Education",
    "testbook": "Education",
    "allen": "Education",
    "aakash": "Education",
    "fiitjee": "Education",
    "1mg": "Health & Medical",
    "pharmeasy": "Health & Medical",
    "medplus": "Health & Medical",
    "apollo pharmacy": "Health & Medical",
    "netmeds": "Health & Medical",
    "healthkart": "Health & Medical",
    "cult fit": "Health & Medical",
    "gold s gym": "Health & Medical",
    "anytime fitness": "Health & Medical",
    "portea": "Health & Medical",
    "mamaearth": "Personal Care",
    "wow skin": "Personal Care",
    "forest essentials": "Personal Care",
    "sugar cosmetics": "Personal Care",
    "lakme salon": "Personal Care",
    "jawed habib": "Personal Care",
    "naturals salon": "Personal Care",
    "fbb": "Personal Care",
    "zerodha": "Investments & Savings",
    "groww": "Investments & Savings",
    "kuvera": "Investments & Savings",
    "coin": "Investments & Savings",
    "etmoney": "Investments & Savings",
    "paytm money": "Investments & Savings",
    "icicidirect": "Investments & Savings",
    "hdfc securities": "Investments & Savings",
    "nippon": "Investments & Savings",
    "sbi mf": "Investments & Savings",
    "atm charges": "Bank Charges & Fees",
    "annual fee": "Bank Charges & Fees",
    "processing fee": "Bank Charges & Fees",
    "penalty": "Bank Charges & Fees",
    "service charge": "Bank Charges & Fees",
    "gst charge": "Bank Charges & Fees",
}

KEYWORD_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(restaurant|cafe|dhaba|biryani|pizza|burger|chicken|sweets)\b", re.IGNORECASE), "Food & Dining"),
    (re.compile(r"\b(supermarket|grocery|vegetables|kirana)\b", re.IGNORECASE), "Groceries"),
    (re.compile(r"\b(recharge|broadband|electricity|wifi|gas bill|water bill)\b", re.IGNORECASE), "Bills & Utilities"),
    (re.compile(r"\b(hospital|clinic|doctor|pharmacy|medicine|lab|diagnostic|health)\b", re.IGNORECASE), "Health & Medical"),
    (re.compile(r"\b(gym|yoga|fitness|salon|spa|grooming)\b", re.IGNORECASE), "Personal Care"),
    (re.compile(r"\b(rent|landlord|nobroker|nestaway|magicbricks|lease|flat rent|apartment rent|house rent)\b", re.IGNORECASE), "Rent & Housing"),
    (re.compile(r"\b(emi|loan|lend|repay)\b", re.IGNORECASE), "EMI & Loans"),
    (re.compile(r"\b(transfer to|sent to|paid to\s+[a-z0-9 .'-]+)\b", re.IGNORECASE), "Transfers"),
    (re.compile(r"\b(imps|neft|rtgs|p2a|p2m|p2p|p2bank|okhdfc|okaxis|oksbi)\b", re.IGNORECASE), "Transfers"),
    (re.compile(r"\b(atm|cash withdrawal|nfs atm|atm wdl)\b", re.IGNORECASE), "Cash Withdrawal"),
    (re.compile(r"\bupi[/\\:-]?[6-9]\d{9}\b", re.IGNORECASE), "Transfers"),
]

REFUND_RULE = re.compile(r"\b(refund|reversal|reversed|cashback|cash back|chargeback|returned|rev|r/)\b", re.IGNORECASE)
DIGIT_ONLY_RULE = re.compile(r"^[0-9]+$")
PUNCTUATION_RULE = re.compile(r"[^a-z0-9]+")


def normalize_merchant(value: str | None) -> str:
    """Normalize a merchant name for deterministic matching and persistence."""
    raw_value = str(value or "").lower().strip()
    raw_value = raw_value.replace("&", " and ")
    raw_value = raw_value.replace("+", " plus ")
    raw_value = raw_value.replace(".", " ")
    normalized = PUNCTUATION_RULE.sub(" ", raw_value)
    return re.sub(r"\s+", " ", normalized).strip()


def is_allowed_category(category: str | None) -> bool:
    """Return True when a category belongs to the canonical MoneyLeak AI category list."""
    return str(category or "") in ALLOWED_CATEGORIES


def get_need_want_waste_type(category: str | None) -> str:
    """Return the need/want/waste label for a category with an unknown fallback."""
    return CATEGORY_NEED_WANT_WASTE.get(str(category or ""), "unknown")


def text_for_matching(transaction: dict[str, Any]) -> str:
    """Build a combined text string from merchant and description fields."""
    merchant = str(transaction.get("merchant") or "")
    description = str(transaction.get("description") or "")
    return f"{merchant} {description}".strip()


def is_refund_description(description: str | None) -> bool:
    """Return True when a description indicates refund or reversal semantics."""
    return bool(REFUND_RULE.search(str(description or "")))


def exact_verified_match(merchant_normalized: str) -> tuple[str, str] | None:
    """Return a verified merchant key and category for an exact normalized merchant match."""
    if merchant_normalized in VERIFIED_MERCHANTS:
        return merchant_normalized, VERIFIED_MERCHANTS[merchant_normalized]
    return None


def contains_verified_match(merchant_normalized: str) -> tuple[str, str] | None:
    """Return a verified merchant match when a known keyword is contained in the merchant."""
    if not merchant_normalized:
        return None
    for keyword, category in VERIFIED_MERCHANTS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", merchant_normalized):
            return keyword, category
    return None


def collapse_repeated_characters(value: str) -> str:
    """Collapse character runs so short merchant typos can still match verified merchants."""
    return re.sub(r"(.)\1{1,}", r"\1", value or "")


def fuzzy_verified_match(merchant_normalized: str) -> tuple[str, str, float] | None:
    """Return the best fuzzy verified merchant match above the accepted threshold."""
    if not merchant_normalized or DIGIT_ONLY_RULE.fullmatch(merchant_normalized):
        return None
    candidates = [merchant_normalized]
    collapsed = collapse_repeated_characters(merchant_normalized)
    if collapsed and collapsed != merchant_normalized:
        candidates.append(collapsed)
    best_match: tuple[str, float] | None = None
    for candidate in candidates:
        match = process.extractOne(candidate, VERIFIED_MERCHANTS.keys(), scorer=fuzz.WRatio)
        if match is None:
            continue
        matched_keyword, score, _ = match
        if best_match is None or float(score) > best_match[1]:
            best_match = (str(matched_keyword), float(score))
    if best_match is not None and best_match[1] >= 85.0:
        matched_keyword, score = best_match
        return matched_keyword, VERIFIED_MERCHANTS[matched_keyword], score
    return None


def keyword_category_match(text: str) -> tuple[str, str] | None:
    """Return the first keyword-rule category match for a transaction text."""
    for pattern, category in KEYWORD_RULES:
        if pattern.search(text):
            return pattern.pattern, category
    return None


def digit_only_transfer_match(merchant_normalized: str, description: str | None = None) -> bool:
    """Return True when a phone-number style merchant should be reviewed as a transfer."""
    combined_text = f"{merchant_normalized} {description or ''}".strip().lower()
    if DIGIT_ONLY_RULE.fullmatch(merchant_normalized) and len(merchant_normalized) >= 8:
        return True
    return bool(re.search(r"\bupi[/\\:-]?[6-9]\d{9}\b", combined_text))
