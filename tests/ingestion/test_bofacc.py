import io
import pytest
from datetime import date
from decimal import Decimal

from ingestion.bofacc import row_to_transaction, ingest


class TestRowToTransaction:
    """Tests for row_to_transaction function."""

    def test_parse_expense_transaction(self):
        """Test parsing a typical expense (charge) transaction."""
        row = [
            "02/14/2025",
            "24137465045001942681814",
            "WHOLEFDS HAR 10221 OAKLAND CA",
            "OAKLAND       CA ",
            "-30.29",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.account_id == 1
        assert transaction.transaction_date == date(2025, 2, 14)
        assert transaction.post_date is None
        assert transaction.description == "WHOLEFDS HAR 10221 OAKLAND CA"
        assert transaction.amount == Decimal("30.29")
        assert transaction.type == "expense"
        assert transaction.bank_category is None
        assert transaction.additional_metadata == {
            "reference_number": "24137465045001942681814",
            "address": "OAKLAND       CA",
        }
        assert isinstance(transaction.id, str)
        assert len(transaction.id) == 64  # SHA256 hash length

    def test_parse_payment_transaction(self):
        """Test parsing a payment (positive amount) as transfer."""
        row = [
            "02/06/2025",
            "03783204320020600082412",
            "PAYMENT - THANK YOU",
            "",
            "60.00",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("60.00")
        assert transaction.type == "transfer"
        assert transaction.description == "PAYMENT - THANK YOU"

    def test_parse_amount_with_commas(self):
        """Test parsing amounts with comma separators."""
        row = [
            "02/08/2025",
            "24116415039237122196219",
            "NEWEGG MARKETPLACE 800-390-1119 CA",
            "800-390-1119  CA ",
            "-1,290.47",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("1290.47")
        assert transaction.type == "expense"

    def test_parse_with_quotes(self):
        """Test parsing payee and address with quotes."""
        row = [
            "02/14/2025",
            "24137465045001942681814",
            '"QUOTED PAYEE"',
            '"QUOTED ADDRESS"',
            "-100.00",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.description == "QUOTED PAYEE"
        assert transaction.additional_metadata == {
            "reference_number": "24137465045001942681814",
            "address": "QUOTED ADDRESS",
        }

    def test_parse_small_amount(self):
        """Test parsing small amounts like DMV fees."""
        row = [
            "02/12/2025",
            "24755425042260427481888",
            "CA DMV FEE 678-7315516 TN",
            "678-7315516   TN ",
            "-0.88",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("0.88")
        assert transaction.type == "expense"

    def test_parse_large_expense(self):
        """Test parsing large expense amounts."""
        row = [
            "01/01/2025",
            "12345678901234567890123",
            "BIG PURCHASE",
            "CITY      ST ",
            "-2,500.99",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.amount == Decimal("2500.99")
        assert transaction.type == "expense"

    def test_empty_address_field(self):
        """Test handling of empty address field."""
        row = [
            "02/06/2025",
            "03783204320020600082412",
            "PAYMENT - THANK YOU",
            "",
            "60.00",
        ]
        account_id = 1

        transaction = row_to_transaction(row, account_id)

        assert transaction.additional_metadata["address"] == ""

    def test_missing_posted_date_raises_error(self):
        """Test that missing posted date raises ValueError."""
        row = ["", "12345", "DESCRIPTION", "ADDRESS", "-100.00"]
        account_id = 1

        with pytest.raises(ValueError, match="Missing required fields"):
            row_to_transaction(row, account_id)

    def test_missing_amount_raises_error(self):
        """Test that missing amount raises ValueError."""
        row = ["02/14/2025", "12345", "DESCRIPTION", "ADDRESS", ""]
        account_id = 1

        with pytest.raises(ValueError, match="Missing required fields"):
            row_to_transaction(row, account_id)

    def test_invalid_date_format_raises_error(self):
        """Test that invalid date format raises ValueError."""
        row = ["2025-02-14", "12345", "DESCRIPTION", "ADDRESS", "-100.00"]
        account_id = 1

        with pytest.raises(ValueError):
            row_to_transaction(row, account_id)

    def test_invalid_amount_format_raises_error(self):
        """Test that invalid amount format raises error."""
        row = ["02/14/2025", "12345", "DESCRIPTION", "ADDRESS", "invalid"]
        account_id = 1

        with pytest.raises(Exception):  # Decimal raises InvalidOperation
            row_to_transaction(row, account_id)

    def test_checksum_consistency(self):
        """Test that same input produces same checksum."""
        row = [
            "02/14/2025",
            "24137465045001942681814",
            "TEST",
            "CITY      ST ",
            "-100.00",
        ]
        account_id = 1

        transaction1 = row_to_transaction(row, account_id)
        transaction2 = row_to_transaction(row, account_id)

        assert transaction1.id == transaction2.id

    def test_checksum_differs_for_different_input(self):
        """Test that different inputs produce different checksums."""
        row1 = [
            "02/14/2025",
            "24137465045001942681814",
            "TEST1",
            "CITY      ST ",
            "-100.00",
        ]
        row2 = [
            "02/14/2025",
            "24137465045001942681814",
            "TEST2",
            "CITY      ST ",
            "-100.00",
        ]
        account_id = 1

        transaction1 = row_to_transaction(row1, account_id)
        transaction2 = row_to_transaction(row2, account_id)

        assert transaction1.id != transaction2.id

    def test_reference_number_changes_checksum(self):
        """Test that different reference numbers produce different checksums."""
        row1 = [
            "02/14/2025",
            "11111111111111111111111",
            "TEST",
            "CITY      ST ",
            "-100.00",
        ]
        row2 = [
            "02/14/2025",
            "22222222222222222222222",
            "TEST",
            "CITY      ST ",
            "-100.00",
        ]
        account_id = 1

        transaction1 = row_to_transaction(row1, account_id)
        transaction2 = row_to_transaction(row2, account_id)

        assert transaction1.id != transaction2.id


class TestIngest:
    """Tests for ingest function."""

    def test_ingest_valid_csv(self):
        """Test ingesting a valid Bank of America Credit Card CSV."""
        csv_content = """Posted Date,Reference Number,Payee,Address,Amount
02/14/2025,24137465045001942681814,"WHOLEFDS HAR 10221 OAKLAND CA","OAKLAND       CA ",-30.29
02/06/2025,03783204320020600082412,"PAYMENT - THANK YOU","",60.00
02/08/2025,24116415039237122196219,"NEWEGG MARKETPLACE 800-390-1119 CA","800-390-1119  CA ",-1290.47
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].description == "WHOLEFDS HAR 10221 OAKLAND CA"
        assert transactions[0].type == "expense"
        assert transactions[0].amount == Decimal("30.29")
        assert transactions[1].description == "PAYMENT - THANK YOU"
        assert transactions[1].type == "transfer"
        assert transactions[1].amount == Decimal("60.00")
        assert transactions[2].description == "NEWEGG MARKETPLACE 800-390-1119 CA"
        assert transactions[2].type == "expense"
        assert transactions[2].amount == Decimal("1290.47")

    def test_ingest_skips_malformed_rows(self):
        """Test that malformed rows are skipped gracefully."""
        csv_content = """Posted Date,Reference Number,Payee,Address,Amount
02/14/2025,24137465045001942681814,"VALID TRANSACTION","OAKLAND CA",-30.29
02/15/2025,INCOMPLETE
,,,
02/16/2025,24137465045001942681815,"ANOTHER VALID","CITY ST",-10.00
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        # Should only get the 2 valid transactions
        assert len(transactions) == 2
        assert transactions[0].description == "VALID TRANSACTION"
        assert transactions[1].description == "ANOTHER VALID"

    def test_ingest_invalid_header_raises_error(self):
        """Test that invalid header raises ValueError."""
        csv_content = """Date,Description,Amount
02/14/2025,TEST,-100.00
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
        csv_content = """Posted Date,Reference Number,Payee,Address,Amount
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 0

    def test_ingest_preserves_transaction_order(self):
        """Test that transactions are returned in order they appear in CSV."""
        csv_content = """Posted Date,Reference Number,Payee,Address,Amount
02/14/2025,11111111111111111111111,FIRST,CITY1 ST,-10.00
02/15/2025,22222222222222222222222,SECOND,CITY2 ST,-20.00
02/16/2025,33333333333333333333333,THIRD,CITY3 ST,-30.00
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
        csv_content = """Posted Date,Reference Number,Payee,Address,Amount
02/14/2025,24137465045001942681814,TEST,CITY ST,-10.00
"""
        source = io.StringIO(csv_content)
        account_id = 99

        transactions = ingest(source, account_id)

        assert transactions[0].account_id == 99

    def test_ingest_handles_various_amount_formats(self):
        """Test ingestion with various amount formats."""
        csv_content = """Posted Date,Reference Number,Payee,Address,Amount
02/14/2025,11111111111111111111111,NO COMMA,CITY ST,-5.00
02/15/2025,22222222222222222222222,WITH COMMA,CITY ST,"-1,234.56"
02/16/2025,33333333333333333333333,POSITIVE LARGE,CITY ST,"10,000.00"
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].amount == Decimal("5.00")
        assert transactions[1].amount == Decimal("1234.56")
        assert transactions[2].amount == Decimal("10000.00")

    def test_ingest_mixed_transaction_types(self):
        """Test that expenses and payments are correctly identified."""
        csv_content = """Posted Date,Reference Number,Payee,Address,Amount
02/14/2025,11111111111111111111111,PURCHASE,CITY ST,-50.00
02/15/2025,22222222222222222222222,PAYMENT - THANK YOU,,500.00
02/16/2025,33333333333333333333333,ANOTHER CHARGE,CITY ST,-25.00
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 3
        assert transactions[0].type == "expense"
        assert transactions[1].type == "transfer"
        assert transactions[2].type == "expense"

    def test_ingest_with_metadata(self):
        """Test that reference numbers and addresses are captured in metadata."""
        csv_content = """Posted Date,Reference Number,Payee,Address,Amount
02/14/2025,24137465045001942681814,GROCERY,OAKLAND CA,-100.00
02/15/2025,98765432109876543210987,GAS STATION,SAN FRANCISCO CA,-50.00
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 2
        assert transactions[0].additional_metadata == {
            "reference_number": "24137465045001942681814",
            "address": "OAKLAND CA",
        }
        assert transactions[1].additional_metadata == {
            "reference_number": "98765432109876543210987",
            "address": "SAN FRANCISCO CA",
        }

    def test_ingest_real_world_sample(self):
        """Test ingesting data similar to the actual sample file."""
        csv_content = """Posted Date,Reference Number,Payee,Address,Amount
02/14/2025,24137465045001942681814,"WHOLEFDS HAR 10221 OAKLAND CA","OAKLAND       CA ",-30.29
02/14/2025,24164075044091007590111,"TARGET 00027672 EMERYVILLE CA","EMERYVILLE    CA ",-47.70
02/14/2025,24427335044710032859206,"SPROUTS FARMERS MAR OAKLAND CA","OAKLAND       CA ",-25.00
02/12/2025,24755425042260427481888,"CA DMV FEE 678-7315516 TN","678-7315516   TN ",-0.88
02/06/2025,03783204320020600082412,"PAYMENT - THANK YOU","",60.00
"""
        source = io.StringIO(csv_content)
        account_id = 1

        transactions = ingest(source, account_id)

        assert len(transactions) == 5
        # Check first transaction
        assert transactions[0].transaction_date == date(2025, 2, 14)
        assert transactions[0].description == "WHOLEFDS HAR 10221 OAKLAND CA"
        assert transactions[0].amount == Decimal("30.29")
        assert transactions[0].type == "expense"
        # Check payment transaction
        assert transactions[4].description == "PAYMENT - THANK YOU"
        assert transactions[4].amount == Decimal("60.00")
        assert transactions[4].type == "transfer"
        # Check small amount transaction
        assert transactions[3].amount == Decimal("0.88")
