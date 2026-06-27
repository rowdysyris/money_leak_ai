"""Defensive bank statement column mapping utilities."""

from __future__ import annotations

from typing import Any

import pandas as pd

COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["date", "txn date", "transaction date", "value date", "posting date", "post date"],
    "description": ["description", "narration", "particulars", "remarks", "details", "transaction details"],
    "debit": ["debit", "withdrawal", "paid", "dr", "withdrawal amt", "withdrawal amount", "debit amount", "amount dr"],
    "credit": ["credit", "deposit", "received", "cr", "deposit amt", "deposit amount", "credit amount", "amount cr"],
    "amount": ["amount", "transaction amount", "total amount due", "minimum amount due"],
    "balance": ["balance", "closing balance", "available balance", "running balance"],
}

REQUIRED_FIELD_MESSAGES: dict[str, tuple[str, str]] = {
    "date": ("MISSING_DATE_COLUMN", "A transaction date column could not be detected."),
    "description": ("MISSING_DESCRIPTION_COLUMN", "A transaction description column could not be detected."),
    "amount": ("MISSING_AMOUNT_COLUMN", "A debit, credit, or amount column could not be detected."),
}


def normalize_column_name(column_name: Any) -> str:
    """Normalize a DataFrame column name for matching."""
    return " ".join(str(column_name).strip().lower().replace("_", " ").replace("-", " ").split())


def build_column_lookup(df: pd.DataFrame) -> dict[str, str]:
    """Build a normalized-name to original-name lookup without mutating the DataFrame."""
    lookup: dict[str, str] = {}
    for column in df.columns:
        normalized = normalize_column_name(column)
        if normalized and normalized not in lookup:
            lookup[normalized] = str(column)
    return lookup


def find_column(df: pd.DataFrame, aliases: list[str]) -> tuple[str | None, float]:
    """Find the best matching column using exact matching before contains matching."""
    lookup = build_column_lookup(df)
    normalized_aliases = [normalize_column_name(alias) for alias in aliases]

    for alias in normalized_aliases:
        if alias in lookup:
            return lookup[alias], 1.0

    for normalized_column, original_column in lookup.items():
        for alias in normalized_aliases:
            if len(alias) >= 4 and alias in normalized_column:
                return original_column, 0.82


    return None, 0.0


def build_mapping_error(code: str, message: str, found_columns: list[str]) -> dict[str, Any]:
    """Build a controlled column mapping error response."""
    return {
        "code": code,
        "message": message,
        "found_columns": found_columns,
        "details": {"found_columns": found_columns},
    }


def map_columns(df: pd.DataFrame) -> dict[str, Any]:
    """Detect date, description, amount, debit, credit, and balance columns in a statement DataFrame."""
    if not isinstance(df, pd.DataFrame):
        return build_mapping_error("INVALID_DATAFRAME", "Input must be a pandas DataFrame.", [])

    found_columns = [str(column) for column in df.columns]
    if df.empty or len(df.columns) == 0:
        return build_mapping_error("EMPTY_TABLE", "No usable columns were found in the uploaded statement.", found_columns)

    mapping: dict[str, str | None | float] = {}
    confidence_scores: list[float] = []

    for field_name, aliases in COLUMN_ALIASES.items():
        column, confidence = find_column(df, aliases)
        mapping[field_name] = column
        if column is not None:
            confidence_scores.append(confidence)

    if mapping["date"] is None:
        code, message = REQUIRED_FIELD_MESSAGES["date"]
        return build_mapping_error(code, message, found_columns)

    if mapping["description"] is None:
        code, message = REQUIRED_FIELD_MESSAGES["description"]
        return build_mapping_error(code, message, found_columns)

    has_amount = mapping["amount"] is not None
    has_debit_or_credit = mapping["debit"] is not None or mapping["credit"] is not None
    if not has_amount and not has_debit_or_credit:
        code, message = REQUIRED_FIELD_MESSAGES["amount"]
        return build_mapping_error(code, message, found_columns)

    required_detected = 3
    optional_detected = len([field for field in ("debit", "credit", "balance") if mapping.get(field) is not None])
    average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    coverage_bonus = min(optional_detected * 0.05, 0.15)
    mapping["mapping_confidence"] = round(min(1.0, (average_confidence * 0.85) + coverage_bonus + (required_detected * 0.0)), 3)
    return mapping


def validate_manual_mapping(df: pd.DataFrame, requested_mapping: dict[str, Any]) -> dict[str, Any]:
    """Validate a user-confirmed mapping against the uploaded file's real columns."""
    if not isinstance(df, pd.DataFrame) or not isinstance(requested_mapping, dict):
        return build_mapping_error("INVALID_COLUMN_MAPPING", "Column mapping must be an object.", [])
    found_columns = [str(column) for column in df.columns]
    allowed_fields = {"date", "description", "debit", "credit", "amount", "balance"}
    mapping: dict[str, Any] = {field: None for field in allowed_fields}
    for field, value in requested_mapping.items():
        if field not in allowed_fields or value in {None, ""}:
            continue
        column = str(value)
        if column not in found_columns:
            return build_mapping_error(
                "INVALID_COLUMN_MAPPING",
                f"Mapped column '{column}' does not exist in the uploaded file.",
                found_columns,
            )
        mapping[field] = column
    if mapping["date"] is None:
        return build_mapping_error("MISSING_DATE_COLUMN", REQUIRED_FIELD_MESSAGES["date"][1], found_columns)
    if mapping["description"] is None:
        return build_mapping_error("MISSING_DESCRIPTION_COLUMN", REQUIRED_FIELD_MESSAGES["description"][1], found_columns)
    if mapping["amount"] is None and mapping["debit"] is None and mapping["credit"] is None:
        return build_mapping_error("MISSING_AMOUNT_COLUMN", REQUIRED_FIELD_MESSAGES["amount"][1], found_columns)
    mapping["mapping_confidence"] = 1.0
    return mapping
