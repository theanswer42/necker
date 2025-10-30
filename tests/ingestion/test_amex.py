import io
import pytest
from datetime import date
from decimal import Decimal

from ingestion.amex import row_to_transaction, ingest


class TestRowToTransaction:
    """Tests for row_to_transaction function."""

    def test_parse_expense_transaction(self):
        """Test parsing a typical expense (charge) transaction."""
        row = [
            "01/15/2025",
            "AMAZON.COM",
            "45.99",
            "",
            "AMAZON.COM*RETAIL",
            "410 TERRY AVE N",
            "SEATTLE, WA",
            "98109",
            "UNITED STATES",
            "12345678901234567",
            "Merchandise & Supplies-Internet Purchase",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.account_id == 1
        assert transaction.transaction_date == date(2025, 1, 15)
        assert transaction.post_date is None  # AMEX doesn't have post date
        assert transaction.description == "AMAZON.COM"
        assert transaction.amount == Decimal("45.99")
        assert transaction.type == "expense"
        assert transaction.bank_category == "Merchandise & Supplies-Internet Purchase"
        assert transaction.additional_metadata["appears_as"] == "AMAZON.COM*RETAIL"
        assert transaction.additional_metadata["address"] == "410 TERRY AVE N"
        assert transaction.additional_metadata["city_state"] == "SEATTLE, WA"
        assert transaction.additional_metadata["zip_code"] == "98109"
        assert transaction.additional_metadata["country"] == "UNITED STATES"
        assert transaction.additional_metadata["reference"] == "12345678901234567"
        assert isinstance(transaction.id, str)
        assert len(transaction.id) == 64

    def test_parse_income_transaction(self):
        """Test parsing a payment/credit (negative amount) as income."""
        row = [
            "01/20/2025",
            "PAYMENT - THANK YOU",
            "-500.00",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Payments",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("500.00")
        assert transaction.type == "income"
        assert transaction.bank_category == "Payments"
        # Empty metadata fields should not be included
        assert (
            transaction.additional_metadata is None
            or len(transaction.additional_metadata) == 0
        )

    def test_parse_transfer_autopay(self):
        """Test parsing AUTOPAY PAYMENT as transfer."""
        row = [
            "01/25/2025",
            "AUTOPAY PAYMENT - THANK YOU",
            "-1250.00",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Payments",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("1250.00")
        assert transaction.type == "transfer"
        assert transaction.description == "AUTOPAY PAYMENT - THANK YOU"

    def test_parse_amount_with_commas(self):
        """Test parsing amounts with comma separators."""
        row = [
            "01/15/2025",
            "BIG PURCHASE",
            "1,234.56",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
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
            '"QUOTED DESCRIPTION"',
            "100.00",
            '"Extended info"',
            '"Statement name"',
            '"123 Main St"',
            '"City, ST"',
            '"12345"',
            '"COUNTRY"',
            "'REF123'",
            '"Category"',
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.description == "QUOTED DESCRIPTION"
        assert transaction.bank_category == "Category"
        assert transaction.additional_metadata["extended_details"] == "Extended info"
        assert transaction.additional_metadata["appears_as"] == "Statement name"
        assert (
            transaction.additional_metadata["reference"] == "REF123"
        )  # Single quotes stripped

    def test_extended_details_in_metadata(self):
        """Test that extended_details is captured in metadata."""
        row = [
            "01/15/2025",
            "RESTAURANT",
            "75.50",
            "Additional transaction details here",
            "",
            "",
            "",
            "",
            "",
            "",
            "Restaurant-Bar & Cafes",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert (
            transaction.additional_metadata["extended_details"]
            == "Additional transaction details here"
        )

    def test_appears_as_same_as_description_not_in_metadata(self):
        """Test that appears_as is not added if same as description."""
        row = [
            "01/15/2025",
            "STORE NAME",
            "50.00",
            "",
            "STORE NAME",  # Same as description
            "",
            "",
            "",
            "",
            "",
            "Shopping",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        # appears_as should not be in metadata if it's the same as description
        assert (
            transaction.additional_metadata is None
            or "appears_as" not in transaction.additional_metadata
        )

    def test_empty_category(self):
        """Test handling of empty category field."""
        row = [
            "01/15/2025",
            "NO CATEGORY",
            "50.00",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.bank_category is None

    def test_minimal_row_format(self):
        """Test parsing minimal row with only required fields."""
        row = ["01/15/2025", "MINIMAL", "50.00"]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.description == "MINIMAL"
        assert transaction.amount == Decimal("50.00")
        assert transaction.bank_category is None
        assert (
            transaction.additional_metadata is None
            or len(transaction.additional_metadata) == 0
        )

    def test_missing_date_raises_error(self):
        """Test that missing date raises ValueError."""
        row = ["", "DESCRIPTION", "100.00", "", "", "", "", "", "", "", "Shopping"]
        account_id = 1

        with pytest.raises(ValueError, match="Missing required fields"):
            row_to_transaction(row, account_id)

    def test_missing_amount_raises_error(self):
        """Test that missing amount raises ValueError."""
        row = [
            "01/15/2025",
            "DESCRIPTION",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Shopping",
        ]
        account_id = 1

        with pytest.raises(ValueError, match="Missing required fields"):
            row_to_transaction(row, account_id)

    def test_invalid_date_format_raises_error(self):
        """Test that invalid date format raises ValueError."""
        row = [
            "2025-01-15",
            "DESCRIPTION",
            "100.00",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Shopping",
        ]
        account_id = 1

        with pytest.raises(ValueError):
            row_to_transaction(row, account_id)

    def test_invalid_amount_format_raises_error(self):
        """Test that invalid amount format raises error."""
        row = [
            "01/15/2025",
            "DESCRIPTION",
            "invalid",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Shopping",
        ]
        account_id = 1

        with pytest.raises(Exception):
            row_to_transaction(row, account_id)

    def test_checksum_consistency(self):
        """Test that same input produces same checksum."""
        row = [
            "01/15/2025",
            "TEST",
            "100.00",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Shopping",
        ]
        account_id = 1

        transaction1 = row_to_transaction(row, account_id)
        transaction2 = row_to_transaction(row, account_id)

        assert transaction1.id == transaction2.id

    def test_reference_changes_checksum(self):
        """Test that different reference numbers produce different checksums."""
        row1 = [
            "01/15/2025",
            "TEST",
            "100.00",
            "",
            "",
            "",
            "",
            "",
            "",
            "REF1",
            "Shopping",
        ]
        row2 = [
            "01/15/2025",
            "TEST",
            "100.00",
            "",
            "",
            "",
            "",
            "",
            "",
            "REF2",
            "Shopping",
        ]
        account_id = 1

        transaction1 = row_to_transaction(row1, account_id)
        transaction2 = row_to_transaction(row2, account_id)

        assert transaction1.id != transaction2.id


class TestIngest:
    """Tests for ingest function."""

    def test_ingest_valid_csv(self):
        """Test ingesting a valid AMEX CSV."""
        csv_content = """Date,Description,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
01/15/2025,STARBUCKS,5.75,,,,,,,12345,Restaurant-Bar & Cafes
01/20/2025,PAYMENT - THANK YOU,-500.00,,,,,,,67890,Payments
01/25/2025,AUTOPAY PAYMENT - THANK YOU,-1250.00,,,,,,,11111,Payments
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].description == "STARBUCKS"
        assert transactions[0].type == "expense"
        assert transactions[1].description == "PAYMENT - THANK YOU"
        assert transactions[1].type == "income"
        assert transactions[2].description == "AUTOPAY PAYMENT - THANK YOU"
        assert transactions[2].type == "transfer"

    def test_ingest_with_full_metadata(self):
        """Test ingesting CSV with all metadata fields populated."""
        csv_content = """Date,Description,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
01/15/2025,AMAZON,100.00,Order details,AMAZON*RETAIL,123 Main St,Seattle WA,98101,USA,987654321,Shopping
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 1
        assert (
            transactions[0].additional_metadata["extended_details"] == "Order details"
        )
        assert transactions[0].additional_metadata["appears_as"] == "AMAZON*RETAIL"
        assert transactions[0].additional_metadata["address"] == "123 Main St"
        assert transactions[0].additional_metadata["city_state"] == "Seattle WA"
        assert transactions[0].additional_metadata["zip_code"] == "98101"
        assert transactions[0].additional_metadata["country"] == "USA"
        assert transactions[0].additional_metadata["reference"] == "987654321"

    def test_ingest_skips_malformed_rows(self):
        """Test that malformed rows are skipped gracefully."""
        csv_content = """Date,Description,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
01/15/2025,VALID,5.75,,,,,,,12345,Shopping
01/16/2025,INCOMPLETE
,,
01/17/2025,ANOTHER VALID,10.00,,,,,,,67890,Shopping
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
01/15/2025,TEST,100.00,Shopping
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
        csv_content = """Date,Description,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 0

    def test_ingest_preserves_transaction_order(self):
        """Test that transactions are returned in order they appear."""
        csv_content = """Date,Description,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
01/15/2025,FIRST,10.00,,,,,,,111,Shopping
01/16/2025,SECOND,20.00,,,,,,,222,Shopping
01/17/2025,THIRD,30.00,,,,,,,333,Shopping
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
        csv_content = """Date,Description,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
01/15/2025,TEST,10.00,,,,,,,111,Shopping
"""
        source = io.StringIO(csv_content)
        account_id = 99

        transactions = ingest(source, account_id)

        assert transactions[0].account_id == 99

    def test_ingest_handles_various_amount_formats(self):
        """Test ingestion with various amount formats."""
        csv_content = """Date,Description,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
01/15/2025,NO COMMA,5.00,,,,,,,111,Shopping
01/16/2025,WITH COMMA,1234.56,,,,,,,222,Shopping
01/17/2025,NEGATIVE LARGE,-10000.00,,,,,,,333,Payments
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
        csv_content = """Date,Description,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
01/15/2025,RESTAURANT,50.00,,,,,,,111,Restaurant-Bar & Cafes
01/16/2025,GAS STATION,40.00,,,,,,,222,Gasoline
01/17/2025,GROCERY STORE,100.00,,,,,,,333,Supermarkets
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].bank_category == "Restaurant-Bar & Cafes"
        assert transactions[1].bank_category == "Gasoline"
        assert transactions[2].bank_category == "Supermarkets"

    def test_ingest_international_transaction(self):
        """Test ingesting international transaction with full location data."""
        csv_content = """Date,Description,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
01/15/2025,FOREIGN PURCHASE,250.00,International transaction,SHOP NAME,456 High St,London,SW1A 1AA,UNITED KINGDOM,999888777,Shopping
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 1
        t = transactions[0]
        assert t.additional_metadata["address"] == "456 High St"
        assert t.additional_metadata["city_state"] == "London"
        assert t.additional_metadata["zip_code"] == "SW1A 1AA"
        assert t.additional_metadata["country"] == "UNITED KINGDOM"
