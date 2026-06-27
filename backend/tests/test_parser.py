"""Parser tests for defensive bank statement ingestion."""

from io import BytesIO

import pandas as pd

from services.merchant_extractor import clean_merchant
from services.statement_parser import parse_statement
from services.transaction_cleaner import clean_transactions


def to_bytes(text: str) -> bytes:
    """Encode inline CSV text as UTF-8 bytes."""
    return text.encode("utf-8")


def parse_and_clean(csv_text: str) -> dict:
    """Parse and clean inline CSV text for service-level tests."""
    parse_result = parse_statement(to_bytes(csv_text), "statement.csv")
    assert parse_result["success"] is True
    data = parse_result["data"]
    return clean_transactions(data["dataframe"], data["column_map"])


def make_excel_bytes(dataframe: pd.DataFrame) -> bytes:
    """Create an in-memory XLSX workbook from a DataFrame."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False)
    return buffer.getvalue()


def get_error_code(result: dict) -> str:
    """Extract the structured error code from a parser response."""
    return result["error"]["code"]


def test_valid_csv():
    """Standard clean CSV parses and cleans correctly."""
    csv_text = "Date,Description,Debit,Credit,Balance\n01-01-2024,UPI/BADASTOOR/9034XXXXXX,250,,1000\n02-01-2024,Salary credited,,5000,6000\n"
    clean_result = parse_and_clean(csv_text)
    assert len(clean_result["transactions"]) == 2
    assert clean_result["transactions"][0]["transaction_type"] == "debit"
    assert clean_result["transactions"][1]["transaction_type"] == "credit"


def test_valid_excel():
    """Standard Excel workbook parses correctly."""
    dataframe = pd.DataFrame(
        [
            {"Date": "01-01-2024", "Description": "Groceries", "Debit": "400", "Credit": "", "Balance": "1000"},
            {"Date": "02-01-2024", "Description": "Salary credited", "Debit": "", "Credit": "5000", "Balance": "6000"},
        ]
    )
    result = parse_statement(make_excel_bytes(dataframe), "statement.xlsx")
    assert result["success"] is True
    clean_result = clean_transactions(result["data"]["dataframe"], result["data"]["column_map"])
    assert len(clean_result["transactions"]) == 2


def test_pdf_upload():
    """PDF uploads return a controlled unsupported error."""
    result = parse_statement(b"%PDF-1.4", "statement.pdf")
    assert result["success"] is False
    assert get_error_code(result) == "PDF_NOT_SUPPORTED"


def test_empty_file():
    """Empty uploads return EMPTY_FILE."""
    result = parse_statement(b"", "statement.csv")
    assert result["success"] is False
    assert get_error_code(result) == "EMPTY_FILE"


def test_wrong_extension():
    """Unsupported extensions return INVALID_FILE_TYPE."""
    result = parse_statement(b"hello", "statement.txt")
    assert result["success"] is False
    assert get_error_code(result) == "INVALID_FILE_TYPE"


def test_csv_with_rupee_symbols():
    """Rupee symbols and INR markers are removed during amount cleaning."""
    csv_text = "Date,Description,Debit,Credit\n01/01/2024,Cafe,₹ 450.00,\n02/01/2024,Refund,,INR 100.00\n"
    clean_result = parse_and_clean(csv_text)
    assert clean_result["transactions"][0]["amount"] == -450.0
    assert clean_result["transactions"][1]["amount"] == 100.0


def test_csv_with_comma_amounts():
    """Comma-separated amount strings are parsed as numeric values."""
    csv_text = 'Date,Description,Debit,Credit\n01/01/2024,Shopping,"1,234.56",\n'
    clean_result = parse_and_clean(csv_text)
    assert clean_result["transactions"][0]["amount"] == -1234.56


def test_missing_date_column():
    """Missing date column returns MISSING_DATE_COLUMN."""
    csv_text = "Description,Debit,Credit\nCafe,120,\n"
    result = parse_statement(to_bytes(csv_text), "statement.csv")
    assert result["success"] is False
    assert get_error_code(result) == "MISSING_DATE_COLUMN"


def test_missing_amount_column():
    """Missing amount-related columns return MISSING_AMOUNT_COLUMN."""
    csv_text = "Date,Description,Balance\n01-01-2024,Cafe,1000\n"
    result = parse_statement(to_bytes(csv_text), "statement.csv")
    assert result["success"] is False
    assert get_error_code(result) == "MISSING_AMOUNT_COLUMN"


def test_metadata_rows():
    """CSV files with metadata rows before the table header are detected correctly."""
    metadata = "\n".join([f"Statement metadata line {index}" for index in range(10)])
    csv_text = f"{metadata}\nTxn Date,Narration,Withdrawal Amt,Deposit Amt,Balance\n01-01-2024,Cafe,120,,1000\n"
    result = parse_statement(to_bytes(csv_text), "statement.csv")
    assert result["success"] is True
    assert result["data"]["metadata"]["detected_header_row"] == 10
    clean_result = clean_transactions(result["data"]["dataframe"], result["data"]["column_map"])
    assert len(clean_result["transactions"]) == 1


def test_mixed_date_formats():
    """Multiple date formats in the same file are handled."""
    csv_text = "Date,Description,Amount\n01-01-2024,Cafe,-100\n02/01/2024,Cafe,-100\n2024-01-03,Cafe,-100\n04 Jan 2024,Cafe,-100\n05-Jan-2024,Cafe,-100\nJan 06 2024,Cafe,-100\n07/01/24,Cafe,-100\n08-01-24,Cafe,-100\n"
    clean_result = parse_and_clean(csv_text)
    assert len(clean_result["transactions"]) == 8


def test_separate_debit_credit_columns():
    """Separate debit and credit columns assign direction correctly."""
    csv_text = "Date,Description,Debit,Credit\n01-01-2024,Cafe,200,\n02-01-2024,Salary,,5000\n"
    clean_result = parse_and_clean(csv_text)
    assert clean_result["transactions"][0]["transaction_type"] == "debit"
    assert clean_result["transactions"][0]["amount"] == -200.0
    assert clean_result["transactions"][1]["transaction_type"] == "credit"
    assert clean_result["transactions"][1]["amount"] == 5000.0


def test_single_signed_amount():
    """Single signed amount column maps positive to credit and negative to debit."""
    csv_text = "Date,Description,Amount\n01-01-2024,Cafe,-200\n02-01-2024,Salary credited,5000\n"
    clean_result = parse_and_clean(csv_text)
    assert clean_result["transactions"][0]["transaction_type"] == "debit"
    assert clean_result["transactions"][1]["transaction_type"] == "credit"


def test_upi_description_merchant():
    """UPI merchant narrations extract a readable merchant."""
    assert clean_merchant("UPI/BADASTOOR/9034XXXXXX") == "Badastoor"


def test_phone_number_description():
    """Phone-number-only UPI narrations are marked as Unknown merchants."""
    csv_text = "Date,Description,Debit,Credit\n01-01-2024,UPI/9034567890/OKHDFC,200,\n"
    clean_result = parse_and_clean(csv_text)
    transaction = clean_result["transactions"][0]
    assert transaction["merchant"] == "Unknown"
    assert transaction["needs_review"] is True


def test_refund_detection():
    """Refund descriptions set is_refund."""
    csv_text = "Date,Description,Debit,Credit\n01-01-2024,REFUND FROM AMAZON,,200\n"
    clean_result = parse_and_clean(csv_text)
    assert clean_result["transactions"][0]["is_refund"] is True


def test_duplicate_rows():
    """Identical transactions are flagged as duplicates."""
    csv_text = "Date,Description,Debit,Credit\n01-01-2024,Cafe,200,\n01-01-2024,Cafe,200,\n"
    clean_result = parse_and_clean(csv_text)
    assert clean_result["transactions"][0]["is_duplicate"] is True
    assert clean_result["transactions"][1]["is_duplicate"] is True


def test_large_file():
    """Files over the configured size limit return FILE_TOO_LARGE."""
    large_bytes = b"a" * (11 * 1024 * 1024)
    result = parse_statement(large_bytes, "statement.csv")
    assert result["success"] is False
    assert get_error_code(result) == "FILE_TOO_LARGE"


def test_malformed_csv():
    """Garbled CSV returns a controlled parsing or mapping error."""
    result = parse_statement(b"\xff\xfe\x00\x00\x80\x81", "statement.csv")
    assert result["success"] is False
    assert get_error_code(result) in {
        "ENCODING_ERROR",
        "CSV_PARSE_ERROR",
        "MISSING_DATE_COLUMN",
        "MISSING_DESCRIPTION_COLUMN",
        "MISSING_AMOUNT_COLUMN",
        "EMPTY_TABLE",
        "FILE_CONTENT_MISMATCH",
    }


def test_empty_descriptions():
    """Rows with empty descriptions are handled without crashing."""
    csv_text = "Date,Description,Debit,Credit\n01-01-2024,,200,\n"
    clean_result = parse_and_clean(csv_text)
    assert len(clean_result["transactions"]) == 1
    assert clean_result["transactions"][0]["merchant"] == "Unknown"
    assert clean_result["transactions"][0]["needs_review"] is True


def test_negative_amounts():
    """Negative values in a single amount column are debit transactions."""
    csv_text = "Date,Description,Amount\n01-01-2024,Cafe,-99.50\n"
    clean_result = parse_and_clean(csv_text)
    assert clean_result["transactions"][0]["transaction_type"] == "debit"
    assert clean_result["transactions"][0]["amount"] == -99.5


def test_missing_balance_column():
    """Statements without a balance column still parse successfully."""
    csv_text = "Date,Description,Debit,Credit\n01-01-2024,Cafe,200,\n"
    result = parse_statement(to_bytes(csv_text), "statement.csv")
    assert result["success"] is True
    assert result["data"]["column_map"]["balance"] is None


def test_bank_preset_detection_for_supported_banks():
    """Synthetic statement samples identify each supported Indian bank preset."""
    samples = {
        "sbi": "sbi statement.csv",
        "hdfc": "hdfc bank statement.csv",
        "icici": "icici bank statement.csv",
        "axis": "axis bank statement.csv",
        "kotak": "kotak mahindra statement.csv",
        "canara": "canara bank statement.csv",
        "union": "union bank statement.csv",
        "paytm": "paytm payments bank statement.csv",
    }
    csv_text = "Date,Narration,Debit,Credit,Balance\n01-01-2024,UPI/Swiggy/OKHDFC,250,,1000\n"
    for expected_key, filename in samples.items():
        result = parse_statement(to_bytes(csv_text), filename)
        assert result["success"] is True
        assert result["data"]["metadata"]["bank_preset"]["key"] == expected_key
        assert result["data"]["metadata"]["bank_preset"]["confidence"] >= 0.75


def test_manual_bank_preset_overrides_auto_detection():
    """Manual upload preset selection is reflected in parser metadata."""
    csv_text = "Date,Description,Debit,Credit\n01-01-2024,Cafe,200,\n"
    result = parse_statement(to_bytes(csv_text), "statement.csv", bank_preset="hdfc")
    assert result["success"] is True
    assert result["data"]["metadata"]["bank_preset"]["key"] == "hdfc"
    assert result["data"]["metadata"]["bank_preset"]["source"] == "manual"


def test_credit_card_statement_hints_are_reported():
    """Credit card due-date and charge hints are exposed as metadata."""
    csv_text = "Transaction Date,Posting Date,Description,Amount\n01-01-2024,02-01-2024,Late fee finance charge,500\nMinimum Amount Due,Payment Due Date,Total Amount Due,\n"
    result = parse_statement(to_bytes(csv_text), "credit_card_statement.csv")
    assert result["success"] is True
    credit_card = result["data"]["metadata"]["credit_card"]
    assert credit_card["is_credit_card_statement"] is True
    assert credit_card["has_posting_date"] is True
    assert credit_card["has_late_fee_or_interest"] is True
