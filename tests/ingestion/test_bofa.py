import io
import pytest
from datetime import date
from decimal import Decimal

from ingestion.bofa import row_to_transaction, ingest


class TestRowToTransaction:
    """Tests for row_to_transaction function."""

    def test_parse_expense_transaction(self):
        """Test parsing a typical expense transaction."""
        row = ["01/15/2025", "STARBUCKS #12345", "-5.75", "1,234.56"]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.account_id == 1
        assert transaction.transaction_date == date(2025, 1, 15)
        assert transaction.post_date is None
        assert transaction.description == "STARBUCKS #12345"
        assert transaction.amount == Decimal("5.75")
        assert transaction.type == "expense"
        assert transaction.bank_category is None
        assert transaction.additional_metadata == {"running_balance": "1,234.56"}
        assert isinstance(transaction.id, str)
        assert len(transaction.id) == 64  # SHA256 hash length

    def test_parse_income_transaction(self):
        """Test parsing an income transaction (no negative sign)."""
        row = ["02/01/2025", "SALARY DEPOSIT", "3500.00", "5,000.00"]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("3500.00")
        assert transaction.type == "income"
        assert transaction.description == "SALARY DEPOSIT"

    def test_parse_amount_with_commas(self):
        """Test parsing amounts with comma separators."""
        row = ["01/15/2025", "BIG PURCHASE", "-1,234.56", "8,765.43"]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("1234.56")
        assert transaction.type == "expense"

    def test_parse_amount_with_quotes(self):
        """Test parsing amounts and descriptions with quotes."""
        row = ["01/15/2025", '"QUOTED DESCRIPTION"', '"-100.00"', '"2,000.00"']
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.description == "QUOTED DESCRIPTION"
        assert transaction.amount == Decimal("100.00")

    def test_detect_discover_credit_card_transfer(self):
        """Test detection of Discover credit card payment as transfer."""
        row = [
            "01/15/2025",
            "DISCOVER DES:E-PAYMENT ID:12345",
            "-150.00",
            "1,000.00",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.type == "transfer"
        assert transaction.amount == Decimal("150.00")

    def test_detect_chase_credit_card_transfer(self):
        """Test detection of Chase credit card payment as transfer."""
        row = ["01/15/2025", "CHASE CREDIT CRD DES:AUTOPAY", "-200.00", "1,000.00"]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.type == "transfer"

    def test_detect_amex_credit_card_transfer(self):
        """Test detection of American Express payment as transfer."""
        row = ["01/15/2025", "AMERICAN EXPRESS DES:ACH PMT", "-300.00", "1,000.00"]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.type == "transfer"

    def test_missing_date_raises_error(self):
        """Test that missing date field raises ValueError."""
        row = ["", "DESCRIPTION", "-100.00", "1,000.00"]
        account_id = 1

        with pytest.raises(ValueError, match="Missing required fields"):
            row_to_transaction(row, account_id)

    def test_missing_amount_raises_error(self):
        """Test that missing amount field raises ValueError."""
        row = ["01/15/2025", "DESCRIPTION", "", "1,000.00"]
        account_id = 1

        with pytest.raises(ValueError, match="Missing required fields"):
            row_to_transaction(row, account_id)

    def test_invalid_date_format_raises_error(self):
        """Test that invalid date format raises ValueError."""
        row = ["2025-01-15", "DESCRIPTION", "-100.00", "1,000.00"]
        account_id = 1

        with pytest.raises(ValueError):
            row_to_transaction(row, account_id)

    def test_invalid_amount_format_raises_error(self):
        """Test that invalid amount format raises ValueError."""
        row = ["01/15/2025", "DESCRIPTION", "invalid", "1,000.00"]
        account_id = 1

        with pytest.raises(Exception):  # Decimal raises InvalidOperation
            row_to_transaction(row, account_id)

    def test_checksum_consistency(self):
        """Test that same input produces same checksum."""
        row = ["01/15/2025", "TEST", "-100.00", "1,000.00"]
        account_id = 1

        transaction1 = row_to_transaction(row, account_id)
        transaction2 = row_to_transaction(row, account_id)

        assert transaction1.id == transaction2.id

    def test_checksum_differs_for_different_input(self):
        """Test that different inputs produce different checksums."""
        row1 = ["01/15/2025", "TEST1", "-100.00", "1,000.00"]
        row2 = ["01/15/2025", "TEST2", "-100.00", "1,000.00"]
        account_id = 1

        transaction1 = row_to_transaction(row1, account_id)
        transaction2 = row_to_transaction(row2, account_id)

        assert transaction1.id != transaction2.id


class TestIngest:
    """Tests for ingest function."""

    def test_ingest_valid_csv(self):
        """Test ingesting a valid BoFA CSV with header and transactions."""
        csv_content = """Summary Section Line 1
Summary Section Line 2
Summary Section Line 3
Summary Section Line 4
Summary Section Line 5

Date,Description,Amount,Running Bal.
01/15/2025,STARBUCKS,-5.75,1234.56
01/16/2025,SALARY DEPOSIT,3500.00,4729.81
01/17/2025,CHASE CREDIT CRD DES:AUTOPAY,-250.00,4479.81
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].description == "STARBUCKS"
        assert transactions[0].type == "expense"
        assert transactions[1].description == "SALARY DEPOSIT"
        assert transactions[1].type == "income"
        assert transactions[2].description == "CHASE CREDIT CRD DES:AUTOPAY"
        assert transactions[2].type == "transfer"

    def test_ingest_skips_malformed_rows(self):
        """Test that malformed rows are skipped gracefully."""
        csv_content = """Summary

Date,Description,Amount,Running Bal.
01/15/2025,VALID,-5.75,1234.56
01/16/2025,INCOMPLETE
,MISSING DATE,-100.00,1000.00
01/17/2025,ANOTHER VALID,-10.00,1224.56
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        # Should only get the 2 valid transactions
        assert len(transactions) == 2
        assert transactions[0].description == "VALID"
        assert transactions[1].description == "ANOTHER VALID"

    def test_ingest_header_not_found_raises_error(self):
        """Test that missing header raises ValueError."""
        csv_content = """Some data
Without proper header
More data
"""
        source = io.StringIO(csv_content)
        account_id = 1

        with pytest.raises(ValueError, match="Could not find expected header row"):
            ingest(source, account_id)

    def test_ingest_empty_file_raises_error(self):
        """Test that empty file raises ValueError."""
        csv_content = ""
        source = io.StringIO(csv_content)
        account_id = 1

        with pytest.raises(ValueError, match="Could not find expected header row"):
            ingest(source, account_id)

    def test_ingest_header_only_returns_empty_list(self):
        """Test that file with only header returns empty list."""
        csv_content = """Date,Description,Amount,Running Bal.
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 0

    def test_ingest_with_summary_section(self):
        """Test that summary section is properly skipped."""
        csv_content = """Beginning balance on 01/01/2025,$1,000.00
Ending balance on 01/31/2025,$1,500.00
Total deposits,$2,000.00
Total withdrawals,$-1,500.00
Account number,****1234

Date,Description,Amount,Running Bal.
01/15/2025,TEST TRANSACTION,-5.75,1234.56
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 1
        assert transactions[0].description == "TEST TRANSACTION"

    def test_ingest_preserves_transaction_order(self):
        """Test that transactions are returned in order they appear in CSV."""
        csv_content = """Date,Description,Amount,Running Bal.
01/15/2025,FIRST,-10.00,1000.00
01/16/2025,SECOND,-20.00,980.00
01/17/2025,THIRD,-30.00,950.00
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].description == "FIRST"
        assert transactions[1].description == "SECOND"
        assert transactions[2].description == "THIRD"

    def test_ingest_different_account_ids(self):
        """Test that account_id is correctly assigned."""
        csv_content = """Date,Description,Amount,Running Bal.
01/15/2025,TEST,-10.00,1000.00
"""
        source = io.StringIO(csv_content)
        account_id = 99

        transactions = ingest(source, account_id)

        assert transactions[0].account_id == 99

    def test_ingest_handles_various_amount_formats(self):
        """Test ingestion with various amount formats."""
        csv_content = """Date,Description,Amount,Running Bal.
01/15/2025,NO COMMA,-5.00,1000.00
01/16/2025,WITH COMMA,"-1,234.56",2000.00
01/17/2025,LARGE POSITIVE,"10,000.00",12000.00
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].amount == Decimal("5.00")
        assert transactions[1].amount == Decimal("1234.56")
        assert transactions[2].amount == Decimal("10000.00")
