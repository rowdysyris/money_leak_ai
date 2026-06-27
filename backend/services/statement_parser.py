"""Completely defensive CSV and Excel bank statement parser."""

from __future__ import annotations

import csv
import logging
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from config import get_settings
from schemas.common import error_response, success_response
from services.bank_presets import detect_bank_preset, detect_credit_card_metadata
from services.column_mapper import COLUMN_ALIASES, map_columns, normalize_column_name, validate_manual_mapping
from services.security import has_path_traversal, sanitize_filename, validate_magic_bytes

logger = logging.getLogger("moneyleak-ai.statement-parser")
settings = get_settings()
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
HEADER_SCAN_LIMIT = 21


def get_file_extension(filename: str) -> str:
    """Return a normalized file extension from a filename."""
    return Path(str(filename or "")).suffix.lower()


def build_parser_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a structured parser error response."""
    return error_response(code, message, details or {})


def validate_file(file_bytes: bytes, filename: str) -> dict[str, Any] | None:
    """Validate file name, type, magic bytes, and size before parsing begins."""
    safe_filename = sanitize_filename(filename)
    if has_path_traversal(filename):
        return build_parser_error(
            "INVALID_FILENAME",
            "The uploaded filename is not allowed.",
            {"filename": safe_filename},
        )
    extension = get_file_extension(safe_filename)
    if extension == ".pdf":
        return build_parser_error(
            "PDF_NOT_SUPPORTED",
            "PDF support is not available yet. Please export your bank statement as CSV or Excel.",
            {"filename": safe_filename},
        )
    if extension not in SUPPORTED_EXTENSIONS:
        return build_parser_error(
            "INVALID_FILE_TYPE",
            "Only CSV, XLSX, and XLS files are supported.",
            {"filename": safe_filename, "supported_extensions": sorted(SUPPORTED_EXTENSIONS)},
        )
    if not file_bytes:
        return build_parser_error("EMPTY_FILE", "The uploaded file is empty.", {"filename": safe_filename})
    max_bytes = int(settings.MAX_UPLOAD_SIZE_MB) * 1024 * 1024
    if len(file_bytes) > max_bytes:
        return build_parser_error(
            "FILE_TOO_LARGE",
            f"The uploaded file exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit.",
            {"size_bytes": len(file_bytes), "max_size_bytes": max_bytes},
        )
    magic_error = validate_magic_bytes(file_bytes, safe_filename)
    if magic_error is not None:
        return build_parser_error(
            str(magic_error.get("code", "FILE_CONTENT_MISMATCH")),
            str(magic_error.get("message", "The uploaded file content does not match its extension.")),
            magic_error.get("details", {}) if isinstance(magic_error.get("details", {}), dict) else {},
        )
    return None


def decode_csv_bytes(file_bytes: bytes) -> tuple[str | None, str | None, dict[str, Any] | None]:
    """Decode CSV bytes using supported encodings in fallback order."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            decoded = file_bytes.decode(encoding)
            return decoded.lstrip("\ufeff"), encoding, None
        except UnicodeDecodeError:
            continue
    return None, None, build_parser_error("ENCODING_ERROR", "The CSV file encoding could not be decoded.", {})


def read_csv_dataframe(file_bytes: bytes, header: int | None = None) -> tuple[pd.DataFrame | None, str | None, dict[str, Any] | None]:
    """Read a CSV file into a DataFrame with defensive encoding fallback."""
    decoded, encoding, error = decode_csv_bytes(file_bytes)
    if error is not None:
        return None, None, error
    try:
        dataframe = pd.read_csv(
            StringIO(decoded or ""),
            header=header,
            dtype=str,
            keep_default_na=False,
            on_bad_lines="skip",
            engine="python",
        )
        return dataframe, encoding, None
    except EmptyDataError:
        return None, encoding, build_parser_error("EMPTY_FILE", "The uploaded file does not contain tabular data.", {})
    except ParserError as exc:
        return None, encoding, build_parser_error("CSV_PARSE_ERROR", "The CSV file could not be parsed.", {"error_type": exc.__class__.__name__})
    except (ValueError, TypeError, OSError, ImportError) as exc:
        return None, encoding, build_parser_error("CSV_PARSE_ERROR", "The CSV file could not be parsed.", {"error_type": exc.__class__.__name__})


def read_excel_dataframe(file_bytes: bytes, extension: str, header: int | None = None) -> tuple[pd.DataFrame | None, dict[str, Any] | None]:
    """Read modern or legacy Excel bytes with the matching pandas engine."""
    try:
        engine = "xlrd" if extension == ".xls" else "openpyxl"
        dataframe = pd.read_excel(BytesIO(file_bytes), header=header, dtype=str, engine=engine)
        return dataframe, None
    except BadZipFile as exc:
        return None, build_parser_error("EXCEL_PARSE_ERROR", "The Excel file is not a valid workbook.", {"error_type": exc.__class__.__name__})
    except ValueError as exc:
        return None, build_parser_error("EXCEL_PARSE_ERROR", "The Excel file could not be parsed.", {"error_type": exc.__class__.__name__})
    except OSError as exc:
        return None, build_parser_error("EXCEL_PARSE_ERROR", "The Excel file could not be parsed.", {"error_type": exc.__class__.__name__})


def count_header_keywords(row_values: list[Any]) -> int:
    """Count how many known statement column keywords appear in a candidate header row."""
    keyword_set = {normalize_column_name(alias) for aliases in COLUMN_ALIASES.values() for alias in aliases}
    score = 0
    joined_values = " | ".join(normalize_column_name(value) for value in row_values if str(value).strip())
    for keyword in keyword_set:
        if keyword and keyword in joined_values:
            score += 1
    return score


def detect_header_row(raw_df: pd.DataFrame) -> int:
    """Detect the most likely real header row among the first statement rows."""
    if raw_df.empty:
        return 0
    best_index = 0
    best_score = -1
    scan_count = min(HEADER_SCAN_LIMIT, len(raw_df.index))
    for row_position in range(scan_count):
        row_values = raw_df.iloc[row_position].tolist()
        score = count_header_keywords(row_values)
        if score > best_score:
            best_score = score
            best_index = row_position
    return int(best_index)


def drop_empty_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that are completely empty after whitespace normalization."""
    if df.empty:
        return df.copy()
    normalized_df = df.copy()
    normalized_df = normalized_df.replace(r"^\s*$", pd.NA, regex=True)
    normalized_df = normalized_df.dropna(how="all").reset_index(drop=True)
    normalized_df.columns = [str(column).lstrip("\ufeff").strip() for column in normalized_df.columns]
    return normalized_df



def detect_csv_header_row(file_bytes: bytes) -> tuple[int | None, str | None, dict[str, Any] | None]:
    """Detect a CSV header row by scanning raw decoded rows before pandas parsing."""
    decoded, encoding, error = decode_csv_bytes(file_bytes)
    if error is not None:
        return None, None, error
    try:
        rows = list(csv.reader(StringIO(decoded or "")))
    except csv.Error as exc:
        return None, encoding, build_parser_error("CSV_PARSE_ERROR", "The CSV file could not be parsed.", {"error_type": exc.__class__.__name__})
    if not rows:
        return 0, encoding, None
    best_index = 0
    best_score = -1
    scan_count = min(HEADER_SCAN_LIMIT, len(rows))
    for row_position in range(scan_count):
        score = count_header_keywords(rows[row_position])
        if score > best_score:
            best_score = score
            best_index = row_position
    return int(best_index), encoding, None

def read_statement_dataframe(file_bytes: bytes, extension: str) -> tuple[pd.DataFrame | None, dict[str, Any], list[str]]:
    """Read a statement file, detect metadata header rows, and return a cleaned DataFrame."""
    warnings: list[str] = []
    metadata: dict[str, Any] = {"detected_header_row": 0, "encoding": None}

    if extension == ".csv":
        header_row, encoding, header_error = detect_csv_header_row(file_bytes)
        metadata["encoding"] = encoding
        if header_error is not None or header_row is None:
            return None, header_error or build_parser_error("CSV_PARSE_ERROR", "The CSV file could not be parsed.", {}), warnings
        metadata["detected_header_row"] = header_row
        if header_row > 0:
            warnings.append(f"Detected and skipped {header_row} metadata rows before the table header.")
        parsed_df, _, parse_error = read_csv_dataframe(file_bytes, header=header_row)
        if parse_error is not None or parsed_df is None:
            return None, parse_error or build_parser_error("CSV_PARSE_ERROR", "The CSV file could not be parsed.", {}), warnings
        return drop_empty_rows(parsed_df), metadata, warnings

    raw_df, excel_error = read_excel_dataframe(file_bytes, extension, header=None)
    if excel_error is not None or raw_df is None:
        return None, excel_error or build_parser_error("EXCEL_PARSE_ERROR", "The Excel file could not be parsed.", {}), warnings
    header_row = detect_header_row(raw_df)
    metadata["detected_header_row"] = header_row
    if header_row > 0:
        warnings.append(f"Detected and skipped {header_row} metadata rows before the table header.")
    parsed_df, parse_error = read_excel_dataframe(file_bytes, extension, header=header_row)
    if parse_error is not None or parsed_df is None:
        return None, parse_error or build_parser_error("EXCEL_PARSE_ERROR", "The Excel file could not be parsed.", {}), warnings
    return drop_empty_rows(parsed_df), metadata, warnings


def build_column_mapping_error(mapping_result: dict[str, Any]) -> dict[str, Any]:
    """Convert a column mapper failure into the standard API error envelope."""
    code = str(mapping_result.get("code", "COLUMN_MAPPING_ERROR"))
    message = str(mapping_result.get("message", "Required statement columns could not be detected."))
    details = mapping_result.get("details", {})
    if not isinstance(details, dict):
        details = {"found_columns": mapping_result.get("found_columns", [])}
    return build_parser_error(code, message, details)


def parse_statement(
    file_bytes: bytes,
    filename: str,
    bank_preset: str | None = None,
    manual_column_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse CSV or Excel bank statement bytes into a mapped DataFrame and structured metadata without crashing."""
    try:
        validation_error = validate_file(file_bytes, filename)
        if validation_error is not None:
            return validation_error

        safe_filename = sanitize_filename(filename)
        extension = get_file_extension(safe_filename)
        dataframe, metadata_or_error, warnings = read_statement_dataframe(file_bytes, extension)
        if dataframe is None:
            return metadata_or_error

        if dataframe.empty:
            return build_parser_error("EMPTY_TABLE", "No transaction rows were found after removing empty rows.", {"filename": filename})

        detected_preset = detect_bank_preset(dataframe, safe_filename, bank_preset)
        metadata_or_error["bank_preset"] = detected_preset
        metadata_or_error["credit_card"] = detect_credit_card_metadata(dataframe)

        column_mapping = validate_manual_mapping(dataframe, manual_column_map) if manual_column_map is not None else map_columns(dataframe)
        if "code" in column_mapping:
            return build_column_mapping_error(column_mapping)
        metadata_or_error["source_columns"] = [str(column) for column in dataframe.columns]
        metadata_or_error["column_map"] = column_mapping
        metadata_or_error["mapping_confidence"] = float(column_mapping.get("mapping_confidence") or 0.0)
        metadata_or_error["manual_mapping_required"] = manual_column_map is None and metadata_or_error["mapping_confidence"] < 0.7

        return success_response(
            {
                "dataframe": dataframe,
                "column_map": column_mapping,
                "total_rows": int(len(dataframe.index)),
                "file_format": extension.lstrip("."),
                "safe_filename": safe_filename,
                "metadata": metadata_or_error,
            },
            warnings,
        )
    except (AttributeError, KeyError, TypeError, ValueError, OSError, RuntimeError, ImportError) as exc:
        logger.warning("Statement parser returned controlled failure: %s", exc.__class__.__name__)
        return build_parser_error("STATEMENT_PARSE_ERROR", "The statement could not be parsed safely.", {"error_type": exc.__class__.__name__})
