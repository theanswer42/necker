"""Tests for Transaction model and create_with_checksum factory."""

import hashlib
from datetime import date


from models.transaction import Transaction


class TestCreateWithChecksum:
    """Tests for Transaction.create_with_checksum()."""

    def test_id_is_sha256_of_raw_data(self):
        raw = "01/15/2024,Coffee,-5.00,995.00"
        t = Transaction.create_with_checksum(
            raw_data=raw,
            account_id=1,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=500,
            transaction_type="expense",
        )
        expected_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert t.id == expected_id
        assert len(t.id) == 64

    def test_same_raw_data_produces_same_id(self):
        raw = "01/15/2024,Coffee,-5.00,995.00"
        t1 = Transaction.create_with_checksum(
            raw_data=raw,
            account_id=1,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=500,
            transaction_type="expense",
        )
        t2 = Transaction.create_with_checksum(
            raw_data=raw,
            account_id=2,  # different account — doesn't affect ID
            transaction_date=date(2024, 2, 1),
            post_date=None,
            description="Other description",
            bank_category=None,
            amount=999,
            transaction_type="income",
        )
        assert t1.id == t2.id

    def test_different_raw_data_produces_different_id(self):
        kwargs = dict(
            account_id=1,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=500,
            transaction_type="expense",
        )
        t1 = Transaction.create_with_checksum(raw_data="row_a", **kwargs)
        t2 = Transaction.create_with_checksum(raw_data="row_b", **kwargs)
        assert t1.id != t2.id

    def test_fields_are_set_correctly(self):
        post = date(2024, 1, 16)
        t = Transaction.create_with_checksum(
            raw_data="raw",
            account_id=42,
            transaction_date=date(2024, 1, 15),
            post_date=post,
            description="Salary",
            bank_category="PAYROLL",
            amount=200000,
            transaction_type="income",
            additional_metadata={"note": "annual bonus"},
        )
        assert t.account_id == 42
        assert t.transaction_date == date(2024, 1, 15)
        assert t.post_date == post
        assert t.description == "Salary"
        assert t.bank_category == "PAYROLL"
        assert t.amount == 200000
        assert t.transaction_type == "income"
        assert t.additional_metadata == {"note": "annual bonus"}

    def test_optional_fields_default_to_none(self):
        t = Transaction.create_with_checksum(
            raw_data="raw",
            account_id=1,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Coffee",
            bank_category=None,
            amount=500,
            transaction_type="expense",
        )
        assert t.post_date is None
        assert t.bank_category is None
        assert t.additional_metadata is None
        assert t.category_id is None
        assert t.auto_category_id is None
        assert t.merchant_name is None
        assert t.auto_merchant_name is None
        assert t.amortize_months is None
        assert t.amortize_end_date is None
        assert t.accrued is False
        assert t.data_import_id == 0

    def test_unicode_raw_data_hashed_correctly(self):
        raw = "01/15/2024,Café,-5.00,995.00"
        t = Transaction.create_with_checksum(
            raw_data=raw,
            account_id=1,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="Café",
            bank_category=None,
            amount=500,
            transaction_type="expense",
        )
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert t.id == expected

    def test_empty_raw_data_produces_valid_id(self):
        t = Transaction.create_with_checksum(
            raw_data="",
            account_id=1,
            transaction_date=date(2024, 1, 15),
            post_date=None,
            description="",
            bank_category=None,
            amount=0,
            transaction_type="expense",
        )
        assert len(t.id) == 64
        assert t.id == hashlib.sha256(b"").hexdigest()
