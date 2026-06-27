"""Indian bank parser preset registry and lightweight format detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class BankPreset:
    """Configuration for a known Indian bank statement family."""

    key: str
    display_name: str
    markers: tuple[str, ...]
    date_aliases: tuple[str, ...]
    description_aliases: tuple[str, ...]
    debit_aliases: tuple[str, ...]
    credit_aliases: tuple[str, ...]
    amount_aliases: tuple[str, ...]
    balance_aliases: tuple[str, ...]


BANK_PRESETS: dict[str, BankPreset] = {
    "sbi": BankPreset("sbi", "SBI", ("state bank of india", "sbi", "ref no./cheque"), ("txn date", "value date"), ("description", "particulars"), ("debit", "withdrawal"), ("credit", "deposit"), ("amount",), ("balance", "closing balance")),
    "hdfc": BankPreset("hdfc", "HDFC Bank", ("hdfc", "hdfc bank", "chq/ref no"), ("date", "value date"), ("narration", "description"), ("withdrawal amt", "debit"), ("deposit amt", "credit"), ("amount",), ("closing balance", "balance")),
    "icici": BankPreset("icici", "ICICI Bank", ("icici", "icici bank"), ("transaction date", "value date"), ("remarks", "particulars"), ("withdrawal amount", "debit"), ("deposit amount", "credit"), ("amount",), ("balance",)),
    "axis": BankPreset("axis", "Axis Bank", ("axis", "axis bank"), ("transaction date", "value date"), ("particulars", "description"), ("debit", "withdrawal"), ("credit", "deposit"), ("amount",), ("balance",)),
    "kotak": BankPreset("kotak", "Kotak Mahindra Bank", ("kotak", "kotak mahindra"), ("date", "transaction date"), ("narration", "description"), ("withdrawal", "debit"), ("deposit", "credit"), ("amount",), ("balance",)),
    "canara": BankPreset("canara", "Canara Bank", ("canara", "canara bank"), ("txn date", "value date"), ("particulars", "description"), ("debit", "withdrawal"), ("credit", "deposit"), ("amount",), ("balance",)),
    "union": BankPreset("union", "Union Bank", ("union bank", "union bank of india"), ("date", "value date"), ("particulars", "description"), ("debit", "withdrawal"), ("credit", "deposit"), ("amount",), ("balance",)),
    "paytm": BankPreset("paytm", "Paytm Payments Bank", ("paytm payments bank", "paytm"), ("date", "transaction date"), ("transaction details", "description"), ("paid", "debit"), ("received", "credit"), ("amount",), ("balance",)),
    "generic": BankPreset("generic", "Generic", ("",), ("date", "transaction date"), ("description", "narration"), ("debit", "withdrawal"), ("credit", "deposit"), ("amount",), ("balance",)),
}


def supported_bank_presets() -> list[dict[str, str]]:
    """Return public metadata for upload selectors and docs."""
    return [{"key": preset.key, "display_name": preset.display_name} for preset in BANK_PRESETS.values()]


def normalize_preset_key(value: str | None) -> str | None:
    """Normalize a user-selected preset key."""
    if not value:
        return None
    key = str(value).strip().lower().replace("_", "-")
    aliases = {"union-bank": "union", "paytm-payments-bank": "paytm", "auto": None}
    return aliases.get(key, key)


def dataframe_text_sample(dataframe: pd.DataFrame) -> str:
    """Return normalized text from headers and early rows for format detection."""
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return ""
    sample_rows = dataframe.head(8).astype(str).to_numpy().flatten().tolist()
    text = " ".join([*(str(column) for column in dataframe.columns), *sample_rows])
    return re.sub(r"\s+", " ", text.lower())


def detect_bank_preset(dataframe: pd.DataFrame, filename: str = "", selected_preset: str | None = None) -> dict[str, Any]:
    """Detect the most likely bank preset from filename, headers, and sample rows."""
    selected_key = normalize_preset_key(selected_preset)
    if selected_key in BANK_PRESETS and selected_key != "generic":
        preset = BANK_PRESETS[selected_key]
        return {"key": preset.key, "display_name": preset.display_name, "confidence": 1.0, "source": "manual"}

    text = f"{filename} {dataframe_text_sample(dataframe)}".lower()
    best_key = "generic"
    best_score = 0
    for key, preset in BANK_PRESETS.items():
        if key == "generic":
            continue
        score = sum(1 for marker in preset.markers if marker and re.search(rf"\b{re.escape(marker)}\b", text))
        if score > best_score:
            best_key = key
            best_score = score
    preset = BANK_PRESETS[best_key]
    confidence = 0.25 if best_key == "generic" else min(0.95, 0.55 + (best_score * 0.2))
    return {"key": preset.key, "display_name": preset.display_name, "confidence": confidence, "source": "auto"}


def detect_credit_card_metadata(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Extract lightweight credit-card statement hints from headers and early cells."""
    text = dataframe_text_sample(dataframe)
    hints = {
        "is_credit_card_statement": bool(re.search(r"credit card|minimum amount due|total amount due|payment due date", text)),
        "has_posting_date": bool(re.search(r"posting date|post date", text)),
        "has_due_date": bool(re.search(r"due date|payment due date", text)),
        "has_minimum_due": "minimum amount due" in text,
        "has_total_due": "total amount due" in text,
        "has_late_fee_or_interest": bool(re.search(r"late fee|finance charge|interest", text)),
    }
    return hints
