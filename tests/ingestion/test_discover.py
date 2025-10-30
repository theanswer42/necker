import io
import pytest
from datetime import date
from decimal import Decimal

from ingestion.discover import row_to_transaction, ingest


class TestRowToTransaction:
    """Tests for row_to_transaction function."""

    def test_parse_expense_transaction(self):
        """Test parsing a typical expense (charge) transaction."""
        row = [
            "01/15/2025",
            "01/16/2025",
            "AMAZON.COM",
            "45.99",
            "Shopping",
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
        assert isinstance(transaction.id, str)
        assert len(transaction.id) == 64

    def test_parse_income_transaction(self):
        """Test parsing a payment/credit (negative amount) as income."""
        row = [
            "01/20/2025",
            "01/21/2025",
            "PAYMENT THANK YOU",
            "-500.00",
            "Payments and Credits",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("500.00")
        assert transaction.type == "income"
        assert transaction.bank_category == "Payments and Credits"

    def test_parse_transfer_directpay(self):
        """Test parsing DIRECTPAY FULL BALANCE as transfer."""
        row = [
            "01/25/2025",
            "01/26/2025",
            "DIRECTPAY FULL BALANCE",
            "-1250.00",
            "Payments and Credits",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("1250.00")
        assert transaction.type == "transfer"
        assert transaction.description == "DIRECTPAY FULL BALANCE"

    def test_parse_amount_with_commas(self):
        """Test parsing amounts with comma separators."""
        row = [
            "01/15/2025",
            "01/16/2025",
            "BIG PURCHASE",
            "1,234.56",
            "Shopping",
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
            "100.00",
            '"Quoted Category"',
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.description == "QUOTED DESCRIPTION"
        assert transaction.bank_category == "Quoted Category"

    def test_empty_category(self):
        """Test handling of empty category field."""
        row = [
            "01/15/2025",
            "01/16/2025",
            "NO CATEGORY",
            "50.00",
            "",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.bank_category is None

    def test_missing_transaction_date_raises_error(self):
        """Test that missing transaction date raises ValueError."""
        row = ["", "01/16/2025", "DESCRIPTION", "100.00", "Shopping"]
        account_id = 1

        with pytest.raises(ValueError, match="Missing required fields"):
            row_to_transaction(row, account_id)

    def test_missing_amount_raises_error(self):
        """Test that missing amount raises ValueError."""
        row = ["01/15/2025", "01/16/2025", "DESCRIPTION", "", "Shopping"]
        account_id = 1

        with pytest.raises(ValueError, match="Missing required fields"):
            row_to_transaction(row, account_id)

    def test_invalid_date_format_raises_error(self):
        """Test that invalid date format raises ValueError."""
        row = ["2025-01-15", "01/16/2025", "DESCRIPTION", "100.00", "Shopping"]
        account_id = 1

        with pytest.raises(ValueError):
            row_to_transaction(row, account_id)

    def test_invalid_amount_format_raises_error(self):
        """Test that invalid amount format raises error."""
        row = ["01/15/2025", "01/16/2025", "DESCRIPTION", "invalid", "Shopping"]
        account_id = 1

        with pytest.raises(Exception):
            row_to_transaction(row, account_id)

    def test_checksum_consistency(self):
        """Test that same input produces same checksum."""
        row = ["01/15/2025", "01/16/2025", "TEST", "100.00", "Shopping"]
        account_id = 1

        transaction1 = row_to_transaction(row, account_id)
        transaction2 = row_to_transaction(row, account_id)

        assert transaction1.id == transaction2.id

    def test_different_post_date_changes_checksum(self):
        """Test that different post dates produce different checksums."""
        row1 = ["01/15/2025", "01/16/2025", "TEST", "100.00", "Shopping"]
        row2 = ["01/15/2025", "01/17/2025", "TEST", "100.00", "Shopping"]
        account_id = 1

        transaction1 = row_to_transaction(row1, account_id)
        transaction2 = row_to_transaction(row2, account_id)

        assert transaction1.id != transaction2.id


class TestIngest:
    """Tests for ingest function."""

    def test_ingest_valid_csv(self):
        """Test ingesting a valid Discover CSV."""
        csv_content = """Trans. Date,Post Date,Description,Amount,Category
01/15/2025,01/16/2025,STARBUCKS,5.75,Restaurants
01/20/2025,01/21/2025,PAYMENT THANK YOU,-500.00,Payments and Credits
01/25/2025,01/26/2025,DIRECTPAY FULL BALANCE,-1250.00,Payments and Credits
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].description == "STARBUCKS"
        assert transactions[0].type == "expense"
        assert transactions[1].description == "PAYMENT THANK YOU"
        assert transactions[1].type == "income"
        assert transactions[2].description == "DIRECTPAY FULL BALANCE"
        assert transactions[2].type == "transfer"

    def test_ingest_skips_malformed_rows(self):
        """Test that malformed rows are skipped gracefully."""
        csv_content = """Trans. Date,Post Date,Description,Amount,Category
01/15/2025,01/16/2025,VALID,5.75,Shopping
01/16/2025,INCOMPLETE
,,MISSING DATES,100.00,Shopping
01/17/2025,01/18/2025,ANOTHER VALID,10.00,Shopping
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
01/15/2025,01/16/2025,TEST,100.00,Shopping
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
        csv_content = """Trans. Date,Post Date,Description,Amount,Category
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 0

    def test_ingest_preserves_transaction_order(self):
        """Test that transactions are returned in order they appear."""
        csv_content = """Trans. Date,Post Date,Description,Amount,Category
01/15/2025,01/16/2025,FIRST,10.00,Shopping
01/16/2025,01/17/2025,SECOND,20.00,Shopping
01/17/2025,01/18/2025,THIRD,30.00,Shopping
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
        csv_content = """Trans. Date,Post Date,Description,Amount,Category
01/15/2025,01/16/2025,TEST,10.00,Shopping
"""
        source = io.StringIO(csv_content)
        account_id = 99

        transactions = ingest(source, account_id)

        assert transactions[0].account_id == 99

    def test_ingest_handles_various_amount_formats(self):
        """Test ingestion with various amount formats."""
        csv_content = """Trans. Date,Post Date,Description,Amount,Category
01/15/2025,01/16/2025,NO COMMA,5.00,Shopping
01/16/2025,01/17/2025,WITH COMMA,1234.56,Shopping
01/17/2025,01/18/2025,NEGATIVE LARGE,-10000.00,Payments and Credits
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].amount == Decimal("5.00")
        assert transactions[1].amount == Decimal("1234.56")
        assert transactions[2].amount == Decimal("10000.00")

    def test_ingest_with_various_categories(self):
        """Test that different categories are properly captured."""
        csv_content = """Trans. Date,Post Date,Description,Amount,Category
01/15/2025,01/16/2025,RESTAURANT,50.00,Restaurants
01/16/2025,01/17/2025,GAS STATION,40.00,Gasoline
01/17/2025,01/18/2025,GROCERY STORE,100.00,Supermarkets
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].bank_category == "Restaurants"
        assert transactions[1].bank_category == "Gasoline"
        assert transactions[2].bank_category == "Supermarkets"
