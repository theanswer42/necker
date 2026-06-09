"""Tests for the UI blueprint routes."""

import csv
import io
import json
from datetime import date

import pytest

from app.app import create_app
from models.transaction import Transaction
from repositories.accounts import AccountRepository
from repositories.categories import CategoryRepository
from repositories.data_imports import DataImportRepository
from repositories.transactions import TransactionRepository


def _make_bofa_csv_bytes(rows):
    """Create a BofA-format CSV as bytes for upload tests."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Description", "", "Summary Amt."])
    writer.writerow(["Beginning balance as of 01/01/2024", "", "1000.00"])
    writer.writerow(["Total credits", "", "500.00"])
    writer.writerow(["Total debits", "", "-200.00"])
    writer.writerow(["Ending balance as of 01/31/2024", "", "1300.00"])
    writer.writerow([])
    writer.writerow(["Date", "Description", "Amount", "Running Bal."])
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode()


@pytest.fixture
def app(test_config, db_manager_with_schema):
    flask_app = create_app(config=test_config, db_manager=db_manager_with_schema)
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def repos(app):
    db = app.db_manager

    class _Repos:
        accounts = AccountRepository(db)
        transactions = TransactionRepository(db)
        categories = CategoryRepository(db)
        data_imports = DataImportRepository(db)

    return _Repos()


@pytest.fixture
def account(repos):
    return repos.accounts.create("bofa_checking", "bofa", "Bank of America Checking")


@pytest.fixture
def category(repos):
    return repos.categories.create("Food", "Food expenses")


@pytest.fixture
def data_import(repos, account):
    return repos.data_imports.create(account_id=account.id, filename=None)


@pytest.fixture
def transaction(repos, account, data_import):
    t = Transaction.create_with_checksum(
        raw_data="ui-row1",
        account_id=account.id,
        transaction_date=date(2025, 3, 15),
        post_date=None,
        description="Grocery Store",
        bank_category="Groceries",
        amount=4200,
        transaction_type="expense",
    )
    t.data_import_id = data_import.id
    return repos.transactions.create(t)


# --- /ui/accounts ---


class TestAccountsUI:
    def test_accounts_returns_200(self, client):
        resp = client.get("/ui/accounts")
        assert resp.status_code == 200

    def test_accounts_empty(self, client):
        html = client.get("/ui/accounts").data.decode()
        assert "No accounts found" in html

    def test_accounts_lists_accounts(self, client, account):
        html = client.get("/ui/accounts").data.decode()
        assert "bofa_checking" in html
        assert "Bank of America Checking" in html

    def test_accounts_renders_table(self, client, account):
        html = client.get("/ui/accounts").data.decode()
        assert "<table" in html
        assert "<th>" in html

    def test_accounts_has_add_account_button(self, client):
        html = client.get("/ui/accounts").data.decode()
        assert "Add Account" in html
        assert "/ui/accounts/new" in html


# --- /ui/accounts/new and POST /ui/accounts ---


class TestAccountCreateUI:
    def test_account_new_returns_200(self, client):
        resp = client.get("/ui/accounts/new")
        assert resp.status_code == 200

    def test_account_new_shows_form(self, client):
        html = client.get("/ui/accounts/new").data.decode()
        assert "<form" in html
        assert 'name="name"' in html
        assert 'name="account_type"' in html
        assert 'name="description"' in html

    def test_account_new_shows_available_types(self, client):
        html = client.get("/ui/accounts/new").data.decode()
        assert "bofa" in html
        assert "chase" in html
        assert "amex" in html

    def test_account_create_success_returns_account_list(self, client):
        resp = client.post(
            "/ui/accounts",
            data={
                "name": "bofa_checking",
                "account_type": "bofa",
                "description": "BofA",
            },
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "bofa_checking" in html

    def test_account_create_invalid_name_returns_400(self, client):
        resp = client.post(
            "/ui/accounts",
            data={"name": "Bad Name", "account_type": "bofa", "description": "BofA"},
        )
        assert resp.status_code == 400

    def test_account_create_invalid_name_shows_error(self, client):
        resp = client.post(
            "/ui/accounts",
            data={"name": "Bad Name", "account_type": "bofa", "description": "BofA"},
        )
        html = resp.data.decode()
        assert "error-box" in html

    def test_account_create_invalid_name_preserves_form_values(self, client):
        resp = client.post(
            "/ui/accounts",
            data={"name": "Bad Name", "account_type": "bofa", "description": "My Desc"},
        )
        html = resp.data.decode()
        assert "My Desc" in html

    def test_account_create_invalid_type_returns_400(self, client):
        resp = client.post(
            "/ui/accounts",
            data={
                "name": "my_account",
                "account_type": "unknown",
                "description": "Desc",
            },
        )
        assert resp.status_code == 400

    def test_account_create_empty_description_returns_400(self, client):
        resp = client.post(
            "/ui/accounts",
            data={"name": "my_account", "account_type": "bofa", "description": ""},
        )
        assert resp.status_code == 400

    def test_account_create_duplicate_name_returns_400(self, client, repos):
        repos.accounts.create("my_account", "bofa", "Existing")
        resp = client.post(
            "/ui/accounts",
            data={"name": "my_account", "account_type": "chase", "description": "New"},
        )
        assert resp.status_code == 400

    def test_account_create_persists_to_db(self, client, repos):
        client.post(
            "/ui/accounts",
            data={"name": "new_account", "account_type": "amex", "description": "Amex"},
        )
        found = repos.accounts.find_by_name("new_account")
        assert found is not None
        assert found.account_type == "amex"


# --- /ui/categories ---


class TestCategoriesUI:
    def test_categories_returns_200(self, client):
        resp = client.get("/ui/categories")
        assert resp.status_code == 200

    def test_categories_empty(self, client):
        html = client.get("/ui/categories").data.decode()
        assert "No categories found" in html

    def test_categories_lists_categories(self, client, category):
        html = client.get("/ui/categories").data.decode()
        assert "Food" in html
        assert "Food expenses" in html


# --- /ui/transactions ---


class TestTransactionsUI:
    def test_transactions_returns_200_with_month(self, client):
        resp = client.get("/ui/transactions?month=2025/03")
        assert resp.status_code == 200

    def test_transactions_defaults_to_current_month(self, client):
        # No month param — should not error
        resp = client.get("/ui/transactions")
        assert resp.status_code == 200

    def test_transactions_invalid_month_returns_400(self, client):
        resp = client.get("/ui/transactions?month=2025-03")
        assert resp.status_code == 400

    def test_transactions_invalid_month_shows_error(self, client):
        html = client.get("/ui/transactions?month=badmonth").data.decode()
        assert "error-box" in html

    def test_transactions_empty_month(self, client):
        html = client.get("/ui/transactions?month=2025/01").data.decode()
        assert "No transactions" in html

    def test_transactions_shows_month_label(self, client):
        html = client.get("/ui/transactions?month=2025/03").data.decode()
        assert "2025/03" in html

    def test_transactions_shows_prev_next_navigation(self, client):
        html = client.get("/ui/transactions?month=2025/03").data.decode()
        assert "2025/02" in html  # prev month
        assert "2025/04" in html  # next month

    def test_transactions_lists_transactions(self, client, transaction):
        html = client.get("/ui/transactions?month=2025/03").data.decode()
        assert "Grocery Store" in html
        assert "42.00" in html  # $42.00

    def test_transactions_renders_table(self, client, transaction):
        html = client.get("/ui/transactions?month=2025/03").data.decode()
        assert "<table" in html

    def test_transactions_year_boundary_prev(self, client):
        # January → prev should be December of previous year
        html = client.get("/ui/transactions?month=2025/01").data.decode()
        assert "2024/12" in html

    def test_transactions_year_boundary_next(self, client):
        # December → next should be January of next year
        html = client.get("/ui/transactions?month=2025/12").data.decode()
        assert "2026/01" in html

    def test_transactions_has_import_button(self, client):
        html = client.get("/ui/transactions?month=2025/03").data.decode()
        assert "Import transactions" in html
        assert "/ui/imports/new" in html


# --- /ui/imports ---


class TestImportUI:
    def test_import_form_returns_200(self, client):
        resp = client.get("/ui/imports/new")
        assert resp.status_code == 200

    def test_import_form_shows_empty_state_without_accounts(self, client):
        html = client.get("/ui/imports/new").data.decode()
        assert "No accounts found" in html

    def test_import_form_shows_accounts(self, client, account):
        html = client.get("/ui/imports/new").data.decode()
        assert "bofa_checking" in html
        assert "<select" in html

    def test_import_upload_without_file_returns_400(self, client, account):
        resp = client.post(
            "/ui/imports",
            data={"account_id": str(account.id)},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "Please select a CSV file" in resp.data.decode()

    def test_import_upload_without_account_returns_400(self, client):
        resp = client.post(
            "/ui/imports",
            data={"account_id": ""},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "Please select an account" in resp.data.decode()

    def test_import_upload_unknown_account_returns_404(self, client):
        resp = client.post(
            "/ui/imports",
            data={
                "account_id": "99999",
                "csv_file": (io.BytesIO(b"data"), "test.csv"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404

    def test_import_upload_valid_csv_redirects_to_review(self, client, account):
        csv_bytes = _make_bofa_csv_bytes(
            [
                ["01/15/2024", "Coffee Shop", "-5.00", "995.00"],
                ["01/20/2024", "Salary", "2000.00", "2995.00"],
            ]
        )
        resp = client.post(
            "/ui/imports",
            data={
                "account_id": str(account.id),
                "csv_file": (io.BytesIO(csv_bytes), "test.csv"),
            },
            content_type="multipart/form-data",
        )
        # New transactions hand off to the batched review flow via HX-Location.
        assert resp.status_code == 200
        location = json.loads(resp.headers["HX-Location"])
        assert location["path"].endswith("/review")
        assert location["target"] == "#content"

    def test_import_review_get_renders_batch(self, client, account):
        csv_bytes = _make_bofa_csv_bytes(
            [
                ["01/15/2024", "Coffee Shop", "-5.00", "995.00"],
                ["01/20/2024", "Salary", "2000.00", "2995.00"],
            ]
        )
        client.post(
            "/ui/imports",
            data={
                "account_id": str(account.id),
                "csv_file": (io.BytesIO(csv_bytes), "test.csv"),
            },
            content_type="multipart/form-data",
        )
        import_id = DataImportRepository(client.application.db_manager).find_all()[0].id
        html = client.get(f"/ui/imports/{import_id}/review").data.decode()
        assert "Review Import" in html
        assert "Coffee Shop" in html
        assert "Salary" in html
        assert "remaining" in html

    def test_import_upload_valid_csv_inserts_transactions(self, client, repos, account):
        csv_bytes = _make_bofa_csv_bytes(
            [["01/15/2024", "Coffee Shop", "-5.00", "995.00"]]
        )
        client.post(
            "/ui/imports",
            data={
                "account_id": str(account.id),
                "csv_file": (io.BytesIO(csv_bytes), "test.csv"),
            },
            content_type="multipart/form-data",
        )
        txns = repos.transactions.find_by_account(account.id)
        assert len(txns) == 1
        assert txns[0].description == "Coffee Shop"

    def test_import_upload_all_duplicates_returns_success(self, client, repos, account):
        csv_bytes = _make_bofa_csv_bytes(
            [["01/15/2024", "Coffee Shop", "-5.00", "995.00"]]
        )
        # First import
        client.post(
            "/ui/imports",
            data={
                "account_id": str(account.id),
                "csv_file": (io.BytesIO(csv_bytes), "test.csv"),
            },
            content_type="multipart/form-data",
        )
        # Second import — all duplicates
        resp = client.post(
            "/ui/imports",
            data={
                "account_id": str(account.id),
                "csv_file": (io.BytesIO(csv_bytes), "test.csv"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Import Complete" in html
        assert "Review Import" not in html

    def test_import_upload_bad_csv_headers_returns_400(self, client, account):
        bad_csv = b"Col1,Col2\nfoo,bar\n"
        resp = client.post(
            "/ui/imports",
            data={
                "account_id": str(account.id),
                "csv_file": (io.BytesIO(bad_csv), "bad.csv"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "error-box" in resp.data.decode()

    def test_import_review_valid_edits_returns_success(self, client, repos, account):
        csv_bytes = _make_bofa_csv_bytes(
            [["01/15/2024", "Coffee Shop", "-5.00", "995.00"]]
        )
        # Upload to get data_import_id
        upload_resp = client.post(
            "/ui/imports",
            data={
                "account_id": str(account.id),
                "csv_file": (io.BytesIO(csv_bytes), "test.csv"),
            },
            content_type="multipart/form-data",
        )
        assert upload_resp.status_code == 200

        # Get data_import_id from db
        txns = repos.transactions.find_by_account(account.id)
        assert len(txns) == 1
        data_import_id = txns[0].data_import_id

        resp = client.post(
            f"/ui/imports/{data_import_id}/review",
            data={
                f"category_id_{txns[0].id}": "",
                f"merchant_name_{txns[0].id}": "Starbucks",
            },
            content_type="application/x-www-form-urlencoded",
        )
        # Saving a batch advances to the next batch via HX-Location.
        assert resp.status_code == 200
        location = json.loads(resp.headers["HX-Location"])
        assert location["path"] == f"/ui/imports/{data_import_id}/review"

        # Verify merchant saved and the transaction is now marked reviewed.
        updated = repos.transactions.find(txns[0].id)
        assert updated.merchant_name == "Starbucks"
        assert updated.import_reviewed is True

        # The next GET shows the completion view (nothing left to review).
        complete = client.get(f"/ui/imports/{data_import_id}/review").data.decode()
        assert "Review Complete" in complete

    def test_import_review_invalid_category_returns_400(self, client, repos, account):
        csv_bytes = _make_bofa_csv_bytes(
            [["01/15/2024", "Coffee Shop", "-5.00", "995.00"]]
        )
        client.post(
            "/ui/imports",
            data={
                "account_id": str(account.id),
                "csv_file": (io.BytesIO(csv_bytes), "test.csv"),
            },
            content_type="multipart/form-data",
        )

        txns = repos.transactions.find_by_account(account.id)
        data_import_id = txns[0].data_import_id

        resp = client.post(
            f"/ui/imports/{data_import_id}/review",
            data={
                f"category_id_{txns[0].id}": "99999",
                f"merchant_name_{txns[0].id}": "",
            },
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 400
        html = resp.data.decode()
        assert "Invalid category" in html

    def test_import_review_unknown_import_returns_404(self, client):
        resp = client.post(
            "/ui/imports/99999/review",
            data={},
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 404

    def test_import_review_saves_category(self, client, repos, account):
        category = repos.categories.create("Food", "Food expenses", None)
        csv_bytes = _make_bofa_csv_bytes(
            [["01/15/2024", "Coffee Shop", "-5.00", "995.00"]]
        )
        client.post(
            "/ui/imports",
            data={
                "account_id": str(account.id),
                "csv_file": (io.BytesIO(csv_bytes), "test.csv"),
            },
            content_type="multipart/form-data",
        )

        txns = repos.transactions.find_by_account(account.id)
        data_import_id = txns[0].data_import_id

        client.post(
            f"/ui/imports/{data_import_id}/review",
            data={
                f"category_id_{txns[0].id}": str(category.id),
                f"merchant_name_{txns[0].id}": "",
            },
            content_type="application/x-www-form-urlencoded",
        )

        updated = repos.transactions.find(txns[0].id)
        assert updated.category_id == category.id


def _insert_unreviewed(repos, account, data_import, n):
    """Insert n unreviewed transactions for an import; return them in date order."""
    created = []
    for i in range(n):
        t = Transaction.create_with_checksum(
            raw_data=f"batchflow-{data_import.id}-{i}",
            account_id=account.id,
            transaction_date=date(2025, 1, 1 + i),
            post_date=None,
            description=f"Txn {i}",
            bank_category=None,
            amount=1000 + i,
            transaction_type="expense",
        )
        t.data_import_id = data_import.id
        repos.transactions.create(t)
        created.append(t)
    return created


class TestImportsListUI:
    def test_imports_list_returns_200(self, client):
        assert client.get("/ui/imports").status_code == 200

    def test_imports_list_empty_state(self, client):
        assert "No imports yet" in client.get("/ui/imports").data.decode()

    def test_imports_list_shows_progress_and_continue(
        self, client, repos, account, data_import
    ):
        _insert_unreviewed(repos, account, data_import, 3)
        html = client.get("/ui/imports").data.decode()
        assert account.name in html
        assert "0 of 3 reviewed" in html
        assert "Continue review" in html

    def test_imports_list_marks_complete(self, client, repos, account, data_import):
        txns = _insert_unreviewed(repos, account, data_import, 1)
        txns[0].import_reviewed = True
        repos.transactions.batch_update(txns, ["import_reviewed"])
        html = client.get("/ui/imports").data.decode()
        assert "1 of 1 reviewed" in html
        assert "Complete" in html


class TestImportReviewBatchFlow:
    def test_get_unknown_import_returns_404(self, client):
        assert client.get("/ui/imports/99999/review").status_code == 404

    def test_get_complete_when_nothing_unreviewed(
        self, client, repos, account, data_import
    ):
        txns = _insert_unreviewed(repos, account, data_import, 1)
        txns[0].import_reviewed = True
        repos.transactions.batch_update(txns, ["import_reviewed"])
        html = client.get(f"/ui/imports/{data_import.id}/review").data.decode()
        assert "Review Complete" in html

    def test_walks_multiple_batches_to_completion(
        self, client, repos, account, data_import
    ):
        # 5 transactions, batch size 2 → 3 batches.
        client.application.config["NECKER_CONFIG"].llm_categorization_batch_size = 2
        _insert_unreviewed(repos, account, data_import, 5)

        review_url = f"/ui/imports/{data_import.id}/review"
        batches_seen = 0
        for _ in range(10):  # generous upper bound to avoid an infinite loop
            if repos.transactions.count_unreviewed(data_import.id) == 0:
                break
            html = client.get(review_url).data.decode()
            assert "Review Import" in html
            batches_seen += 1

            # Submit only the rows in the current batch.
            batch = repos.transactions.find_next_unreviewed_batch(data_import.id, 2)
            assert 1 <= len(batch) <= 2
            form = {}
            for t in batch:
                form[f"category_id_{t.id}"] = ""
                form[f"merchant_name_{t.id}"] = ""
            resp = client.post(
                review_url,
                data=form,
                content_type="application/x-www-form-urlencoded",
            )
            location = json.loads(resp.headers["HX-Location"])
            assert location["path"] == review_url

        assert batches_seen == 3
        assert repos.transactions.count_unreviewed(data_import.id) == 0
        for t in repos.transactions.find_by_data_import_id(data_import.id):
            assert t.import_reviewed is True

        # Final GET shows the completion view.
        assert "Review Complete" in client.get(review_url).data.decode()
