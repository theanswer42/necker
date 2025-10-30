import io
import pytest
from datetime import date
from decimal import Decimal

from ingestion.chase import row_to_transaction, ingest


class TestRowToTransaction:
    """Tests for row_to_transaction function."""

    def test_parse_expense_transaction(self):
        """Test parsing a typical expense (charge) transaction."""
        row = [
            "01/15/2025",
            "01/16/2025",
            "AMAZON.COM",
            "Shopping",
            "Sale",
            "-45.99",
            "",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.account_id == 1
        assert transaction.transaction_date == date(2025, 1, 15)
        assert transaction.post_date == date(2025, 1, 16)
        assert transaction.description == "AMAZON.COM"
        assert transaction.amount == Decimal("45.99")
        assert transaction.type == "expense"
        assert transaction.bank_category == "Shopping"
        assert transaction.additional_metadata is None
        assert isinstance(transaction.id, str)
        assert len(transaction.id) == 64

    def test_parse_income_transaction(self):
        """Test parsing a refund/return (positive amount) as income."""
        row = [
            "01/20/2025",
            "01/21/2025",
            "RETURN REFUND",
            "Shopping",
            "Return",
            "50.00",
            "",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("50.00")
        assert transaction.type == "income"

    def test_parse_transfer_payment_type(self):
        """Test parsing transaction with Type='Payment' as transfer."""
        row = [
            "01/25/2025",
            "01/26/2025",
            "ONLINE PAYMENT",
            "Payments and Credits",
            "Payment",
            "500.00",
            "",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("500.00")
        assert transaction.type == "transfer"
        assert transaction.description == "ONLINE PAYMENT"

    def test_parse_transfer_automatic_payment(self):
        """Test parsing AUTOMATIC PAYMENT in description as transfer."""
        row = [
            "01/25/2025",
            "01/26/2025",
            "AUTOMATIC PAYMENT - THANK YOU",
            "Payments and Credits",
            "Sale",
            "1250.00",
            "",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("1250.00")
        assert transaction.type == "transfer"

    def test_parse_with_memo(self):
        """Test parsing transaction with memo field."""
        row = [
            "01/15/2025",
            "01/16/2025",
            "GROCERY STORE",
            "Food & Drink",
            "Sale",
            "-100.50",
            "Weekly shopping",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("100.50")
        assert transaction.additional_metadata == {"memo": "Weekly shopping"}

    def test_parse_amount_with_commas(self):
        """Test parsing amounts with comma separators."""
        row = [
            "01/15/2025",
            "01/16/2025",
            "BIG PURCHASE",
            "Shopping",
            "Sale",
            "-1,234.56",
            "",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("1234.56")
        assert transaction.type == "expense"

    def test_parse_with_quotes(self):
        """Test parsing descriptions and categories with quotes."""
        row = [
            "01/15/2025",
            "01/16/2025",
            '"QUOTED DESCRIPTION"',
            '"Quoted Category"',
            "Sale",
            "-100.00",
            '"Quoted memo"',
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.description == "QUOTED DESCRIPTION"
        assert transaction.bank_category == "Quoted Category"
        assert transaction.additional_metadata == {"memo": "Quoted memo"}

    def test_empty_category(self):
        """Test handling of empty category field."""
        row = [
            "01/15/2025",
            "01/16/2025",
            "NO CATEGORY",
            "",
            "Sale",
            "-50.00",
            "",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.bank_category is None

    def test_row_without_memo_field(self):
        """Test parsing row with only 6 fields (no memo)."""
        row = [
            "01/15/2025",
            "01/16/2025",
            "OLD FORMAT",
            "Shopping",
            "Sale",
            "-50.00",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.description == "OLD FORMAT"
        assert transaction.additional_metadata is None

    def test_missing_transaction_date_raises_error(self):
        """Test that missing transaction date raises ValueError."""
        row = ["", "01/16/2025", "DESCRIPTION", "Shopping", "Sale", "-100.00", ""]
        account_id = 1

        with pytest.raises(ValueError, match="Missing required fields"):
            row_to_transaction(row, account_id)

    def test_missing_amount_raises_error(self):
        """Test that missing amount raises ValueError."""
        row = ["01/15/2025", "01/16/2025", "DESCRIPTION", "Shopping", "Sale", "", ""]
        account_id = 1

        with pytest.raises(ValueError, match="Missing required fields"):
            row_to_transaction(row, account_id)

    def test_invalid_date_format_raises_error(self):
        """Test that invalid date format raises ValueError."""
        row = [
            "2025-01-15",
            "01/16/2025",
            "DESCRIPTION",
            "Shopping",
            "Sale",
            "-100.00",
            "",
        ]
        account_id = 1

        with pytest.raises(ValueError):
            row_to_transaction(row, account_id)

    def test_invalid_amount_format_raises_error(self):
        """Test that invalid amount format raises error."""
        row = [
            "01/15/2025",
            "01/16/2025",
            "DESCRIPTION",
            "Shopping",
            "Sale",
            "invalid",
            "",
        ]
        account_id = 1

        with pytest.raises(Exception):
            row_to_transaction(row, account_id)

    def test_checksum_consistency(self):
        """Test that same input produces same checksum."""
        row = [
            "01/15/2025",
            "01/16/2025",
            "TEST",
            "Shopping",
            "Sale",
            "-100.00",
            "",
        ]
        account_id = 1

        transaction1 = row_to_transaction(row, account_id)
        transaction2 = row_to_transaction(row, account_id)

        assert transaction1.id == transaction2.id

    def test_memo_changes_checksum(self):
        """Test that different memos produce different checksums."""
        row1 = [
            "01/15/2025",
            "01/16/2025",
            "TEST",
            "Shopping",
            "Sale",
            "-100.00",
            "memo1",
        ]
        row2 = [
            "01/15/2025",
            "01/16/2025",
            "TEST",
            "Shopping",
            "Sale",
            "-100.00",
            "memo2",
        ]
        account_id = 1

        transaction1 = row_to_transaction(row1, account_id)
        transaction2 = row_to_transaction(row2, account_id)

        assert transaction1.id != transaction2.id


class TestIngest:
    """Tests for ingest function."""

    def test_ingest_valid_csv(self):
        """Test ingesting a valid Chase CSV."""
        csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2025,01/16/2025,STARBUCKS,Food & Drink,Sale,-5.75,
01/20/2025,01/21/2025,REFUND,Shopping,Return,50.00,
01/25/2025,01/26/2025,AUTOMATIC PAYMENT - THANK YOU,Payments,Sale,1250.00,
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].description == "STARBUCKS"
        assert transactions[0].type == "expense"
        assert transactions[1].description == "REFUND"
        assert transactions[1].type == "income"
        assert transactions[2].description == "AUTOMATIC PAYMENT - THANK YOU"
        assert transactions[2].type == "transfer"

    def test_ingest_skips_malformed_rows(self):
        """Test that malformed rows are skipped gracefully."""
        csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2025,01/16/2025,VALID,Shopping,Sale,-5.75,
01/16/2025,INCOMPLETE
,,,,,
01/17/2025,01/18/2025,ANOTHER VALID,Shopping,Sale,-10.00,
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 2
        assert transactions[0].description == "VALID"
        assert transactions[1].description == "ANOTHER VALID"

    def test_ingest_invalid_header_raises_error(self):
        """Test that invalid header raises ValueError."""
        csv_content = """Date,Description,Amount,Category
01/15/2025,TEST,-100.00,Shopping
"""
        source = io.StringIO(csv_content)
        account_id = 1

        with pytest.raises(ValueError, match="CSV headers do not match"):
            ingest(source, account_id)

    def test_ingest_empty_file_raises_error(self):
        """Test that empty file raises ValueError."""
        csv_content = ""
        source = io.StringIO(csv_content)
        account_id = 1

        with pytest.raises(ValueError, match="Empty CSV file"):
            ingest(source, account_id)

    def test_ingest_header_only_returns_empty_list(self):
        """Test that file with only header returns empty list."""
        csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 0

    def test_ingest_preserves_transaction_order(self):
        """Test that transactions are returned in order they appear."""
        csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2025,01/16/2025,FIRST,Shopping,Sale,-10.00,
01/16/2025,01/17/2025,SECOND,Shopping,Sale,-20.00,
01/17/2025,01/18/2025,THIRD,Shopping,Sale,-30.00,
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
        csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2025,01/16/2025,TEST,Shopping,Sale,-10.00,
"""
        source = io.StringIO(csv_content)
        account_id = 99

        transactions = ingest(source, account_id)

        assert transactions[0].account_id == 99

    def test_ingest_handles_various_amount_formats(self):
        """Test ingestion with various amount formats."""
        csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2025,01/16/2025,NO COMMA,Shopping,Sale,-5.00,
01/16/2025,01/17/2025,WITH COMMA,Shopping,Sale,-1234.56,
01/17/2025,01/18/2025,POSITIVE LARGE,Returns,Return,10000.00,
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].amount == Decimal("5.00")
        assert transactions[1].amount == Decimal("1234.56")
        assert transactions[2].amount == Decimal("10000.00")

    def test_ingest_with_various_transaction_types(self):
        """Test that different type fields are handled correctly."""
        csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2025,01/16/2025,PURCHASE,Shopping,Sale,-50.00,
01/16/2025,01/17/2025,PAYMENT,Payments,Payment,500.00,
01/17/2025,01/18/2025,RETURN,Shopping,Return,25.00,
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].type == "expense"
        assert transactions[1].type == "transfer"
        assert transactions[2].type == "income"

    def test_ingest_with_memos(self):
        """Test that memo fields are properly captured in metadata."""
        csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2025,01/16/2025,GROCERY,Food,Sale,-100.00,Weekly shopping
01/16/2025,01/17/2025,GAS,Auto,Sale,-50.00,Fill up
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 2
        assert transactions[0].additional_metadata == {"memo": "Weekly shopping"}
        assert transactions[1].additional_metadata == {"memo": "Fill up"}
