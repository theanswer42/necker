"""Tests for the per-import review repository methods on TransactionRepository
and DataImportRepository.find_all."""

from datetime import date

from models.transaction import Transaction


def _make_transaction(
    account_id, data_import_id, raw_suffix, txn_date=None, reviewed=False
):
    t = Transaction.create_with_checksum(
        raw_data=f"review_row_{raw_suffix}",
        account_id=account_id,
        transaction_date=txn_date or date(2025, 3, 15),
        post_date=None,
        description=f"Transaction {raw_suffix}",
        bank_category=None,
        amount=1000,
        transaction_type="expense",
    )
    t.data_import_id = data_import_id
    t.import_reviewed = reviewed
    return t


class TestFindNextUnreviewedBatch:
    def test_returns_only_unreviewed_for_import(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, None)
        unreviewed = services.transactions.create(
            _make_transaction(account.id, di.id, "u", reviewed=False)
        )
        services.transactions.create(
            _make_transaction(account.id, di.id, "r", reviewed=True)
        )

        batch = services.transactions.find_next_unreviewed_batch(di.id, 10)
        assert [t.id for t in batch] == [unreviewed.id]

    def test_excludes_other_imports(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di1 = services.data_imports.create(account.id, None)
        di2 = services.data_imports.create(account.id, None)
        services.transactions.create(_make_transaction(account.id, di1.id, "x"))
        services.transactions.create(_make_transaction(account.id, di2.id, "y"))

        batch = services.transactions.find_next_unreviewed_batch(di1.id, 10)
        assert len(batch) == 1

    def test_respects_limit_and_orders_by_date(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, None)
        services.transactions.create(
            _make_transaction(account.id, di.id, "late", date(2025, 3, 20))
        )
        early = services.transactions.create(
            _make_transaction(account.id, di.id, "early", date(2025, 3, 10))
        )

        batch = services.transactions.find_next_unreviewed_batch(di.id, 1)
        assert len(batch) == 1
        assert batch[0].id == early.id

    def test_empty_when_all_reviewed(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, None)
        services.transactions.create(
            _make_transaction(account.id, di.id, "r", reviewed=True)
        )
        assert services.transactions.find_next_unreviewed_batch(di.id, 10) == []


class TestCountHelpers:
    def test_count_unreviewed_and_total(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, None)
        services.transactions.create(
            _make_transaction(account.id, di.id, "1", reviewed=False)
        )
        services.transactions.create(
            _make_transaction(account.id, di.id, "2", reviewed=False)
        )
        services.transactions.create(
            _make_transaction(account.id, di.id, "3", reviewed=True)
        )

        assert services.transactions.count_by_data_import(di.id) == 3
        assert services.transactions.count_unreviewed(di.id) == 2

    def test_counts_zero_for_unknown_import(self, services):
        assert services.transactions.count_by_data_import(99999) == 0
        assert services.transactions.count_unreviewed(99999) == 0


class TestBatchUpdateImportReviewed:
    def test_batch_update_persists_import_reviewed(self, services):
        account = services.accounts.create("a", "bofa", "A")
        di = services.data_imports.create(account.id, None)
        t = services.transactions.create(
            _make_transaction(account.id, di.id, "1", reviewed=False)
        )

        t.import_reviewed = True
        updated = services.transactions.batch_update([t], ["import_reviewed"])
        assert updated == 1

        refetched = services.transactions.find(t.id)
        assert refetched.import_reviewed is True


class TestDataImportFindAll:
    def test_orders_by_created_at_desc(self, services):
        account = services.accounts.create("a", "bofa", "A")
        first = services.data_imports.create(account.id, "first.csv.gz")
        second = services.data_imports.create(account.id, "second.csv.gz")

        result = services.data_imports.find_all()
        # Newest first; created_at ties broken by id DESC.
        assert [d.id for d in result] == [second.id, first.id]

    def test_empty_when_no_imports(self, services):
        assert services.data_imports.find_all() == []
