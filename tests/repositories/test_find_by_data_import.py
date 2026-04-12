"""Tests for TransactionRepository.find_by_data_import_id."""

from datetime import date

from models.transaction import Transaction


def _make_transaction(account_id, data_import_id, raw_suffix, txn_date=None):
    t = Transaction.create_with_checksum(
        raw_data=f"fdi_row_{raw_suffix}",
        account_id=account_id,
        transaction_date=txn_date or date(2025, 3, 15),
        post_date=None,
        description=f"Transaction {raw_suffix}",
        bank_category=None,
        amount=1000,
        transaction_type="expense",
    )
    t.data_import_id = data_import_id
    return t


class TestFindByDataImportId:
    def test_returns_transactions_for_import(self, services):
        account = services.accounts.create("test", "bofa", "Test")
        di = services.data_imports.create(account.id, None)
        t1 = services.transactions.create(_make_transaction(account.id, di.id, "a"))
        t2 = services.transactions.create(_make_transaction(account.id, di.id, "b"))

        result = services.transactions.find_by_data_import_id(di.id)
        result_ids = {t.id for t in result}

        assert t1.id in result_ids
        assert t2.id in result_ids

    def test_returns_empty_list_for_unknown_import(self, services):
        result = services.transactions.find_by_data_import_id(99999)
        assert result == []

    def test_excludes_transactions_from_other_imports(self, services):
        account = services.accounts.create("test2", "bofa", "Test2")
        di1 = services.data_imports.create(account.id, None)
        di2 = services.data_imports.create(account.id, None)

        t1 = services.transactions.create(_make_transaction(account.id, di1.id, "x"))
        services.transactions.create(_make_transaction(account.id, di2.id, "y"))

        result = services.transactions.find_by_data_import_id(di1.id)
        assert len(result) == 1
        assert result[0].id == t1.id

    def test_ordered_by_transaction_date_ascending(self, services):
        account = services.accounts.create("test3", "bofa", "Test3")
        di = services.data_imports.create(account.id, None)

        t_later = services.transactions.create(
            _make_transaction(account.id, di.id, "later", date(2025, 3, 20))
        )
        t_earlier = services.transactions.create(
            _make_transaction(account.id, di.id, "earlier", date(2025, 3, 10))
        )

        result = services.transactions.find_by_data_import_id(di.id)
        assert result[0].id == t_earlier.id
        assert result[1].id == t_later.id
