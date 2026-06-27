"""Merchant extraction helpers for messy transaction narrations."""

from __future__ import annotations

import re

TRANSFER_PREFIX_PATTERN = re.compile(r"^(UPI|NEFT|IMPS|RTGS|POS|ATM|ACH|NACH|ECOM)[/\\:\-\s]+", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"\b[6-9]\d{9}\b")
REFERENCE_PATTERN = re.compile(r"\b(?:P2A|P2M|TXN|UTR|RRN|REF|UPIREF|ID|NO)[:\-/]?[A-Z0-9]{4,}\b", re.IGNORECASE)
LONG_CODE_PATTERN = re.compile(r"\b[A-Z]*\d{4,}[A-Z0-9]*\b", re.IGNORECASE)
VPA_PATTERN = re.compile(r"@[a-z0-9._-]+", re.IGNORECASE)
NON_MERCHANT_TOKENS = {
    "upi",
    "neft",
    "imps",
    "rtgs",
    "pos",
    "atm",
    "p2a",
    "p2m",
    "okhdfc",
    "okaxis",
    "okicici",
    "oksbi",
    "ybl",
    "paytm",
    "apl",
    "ibl",
    "axisbank",
    "hdfcbank",
    "icici",
    "sbi",
    "txn",
    "ref",
    "rrn",
    "utr",
    "payment",
    "transfer",
    "collect",
}


def normalize_spacing(value: str) -> str:
    """Collapse separators and whitespace into single spaces."""
    cleaned = re.sub(r"[/\\|:_\-]+", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def remove_known_noise(description: str) -> str:
    """Remove common UPI, transfer, reference, phone, and VPA noise from a narration."""
    value = str(description or "").strip()
    value = TRANSFER_PREFIX_PATTERN.sub("", value)
    value = VPA_PATTERN.sub("", value)
    value = PHONE_PATTERN.sub("", value)
    value = REFERENCE_PATTERN.sub("", value)
    value = LONG_CODE_PATTERN.sub("", value)
    return normalize_spacing(value)


def clean_merchant(description: str) -> str:
    """Extract a stable title-cased merchant name from a transaction description."""
    if description is None:
        return "Unknown"

    raw_value = str(description).strip()
    if not raw_value:
        return "Unknown"

    without_noise = remove_known_noise(raw_value)
    tokens = []
    for token in without_noise.split():
        normalized_token = re.sub(r"[^A-Za-z0-9&.' ]", "", token).strip()
        if not normalized_token:
            continue
        if normalized_token.lower() in NON_MERCHANT_TOKENS:
            continue
        if normalized_token.isdigit():
            continue
        tokens.append(normalized_token)

    merchant = " ".join(tokens).strip()
    merchant = re.sub(r"\s+", " ", merchant)
    if not merchant or merchant.isdigit():
        return "Unknown"
    if len(merchant) <= 2 and merchant.lower() in NON_MERCHANT_TOKENS:
        return "Unknown"
    return merchant.title()


def merchant_needs_review(merchant: str) -> bool:
    """Return True when a merchant value is too weak for automatic trust."""
    if merchant is None:
        return True
    normalized = str(merchant).strip()
    return not normalized or normalized == "Unknown" or normalized.isdigit()
