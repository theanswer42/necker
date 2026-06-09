"""UI route definitions — server-rendered HTML fragments for htmx."""

import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

from flask import render_template, request, current_app, make_response

from app.ui import ui_bp
from repositories.accounts import AccountRepository
from repositories.budgets import BudgetRepository
from repositories.categories import CategoryRepository
from repositories.data_imports import DataImportRepository
from repositories.transactions import TransactionRepository
from reports.accrual_spending_summary import AccrualSpendingSummaryReport
from reports.cash_spending_summary import CashSpendingSummaryReport
from reports.month_transactions import MonthTransactionsReport


def _parse_month(value: str):
    """Parse a YYYY/MM string. Returns (year, month) or raises ValueError."""
    year_str, month_str = value.split("/")
    year = int(year_str)
    month = int(month_str)
    if not (1 <= month <= 12):
        raise ValueError(f"month {month} out of range")
    return year, month


def _adjacent_months(year: int, month: int):
    """Return (prev_year, prev_month, next_year, next_month) for navigation."""
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    return prev_year, prev_month, next_year, next_month


@ui_bp.route("/transactions")
def transactions():
    month_raw = request.args.get("month")

    if month_raw:
        try:
            year, month = _parse_month(month_raw)
        except (ValueError, AttributeError):
            return render_template(
                "fragments/transaction_list.html",
                error=f"Invalid month format '{month_raw}'. Use YYYY/MM.",
                transactions=[],
                categories={},
                month_label=None,
                prev_month=None,
                next_month=None,
            ), 400
    else:
        today = date.today()
        year, month = today.year, today.month

    txns = TransactionRepository(current_app.db_manager).get_transactions_by_month(
        year, month
    )

    # Build category lookup for display
    all_categories = CategoryRepository(current_app.db_manager).find_all()
    categories = {c.id: c.name for c in all_categories}

    month_label = f"{year:04d}/{month:02d}"
    prev_year, prev_month, next_year, next_month = _adjacent_months(year, month)

    return render_template(
        "fragments/transaction_list.html",
        error=None,
        transactions=txns,
        categories=categories,
        month_label=month_label,
        prev_month=f"{prev_year:04d}/{prev_month:02d}",
        next_month=f"{next_year:04d}/{next_month:02d}",
    )


@ui_bp.route("/accounts")
def accounts():
    all_accounts = AccountRepository(current_app.db_manager).find_all()
    return render_template("fragments/account_list.html", accounts=all_accounts)


@ui_bp.route("/accounts/new")
def account_new():
    from ingestion import get_available_modules

    return render_template(
        "fragments/account_form.html",
        available_types=get_available_modules(),
        error=None,
        form_data={},
    )


@ui_bp.route("/accounts", methods=["POST"])
def account_create():
    from ingestion import get_available_modules
    from services.accounts import AccountService

    name = request.form.get("name", "").strip()
    account_type = request.form.get("account_type", "").strip()
    description = request.form.get("description", "").strip()
    form_data = {"name": name, "account_type": account_type, "description": description}

    try:
        AccountService(current_app.db_manager).create_account(
            name, account_type, description
        )
    except ValueError as e:
        return (
            render_template(
                "fragments/account_form.html",
                available_types=get_available_modules(),
                error=str(e),
                form_data=form_data,
            ),
            400,
        )

    all_accounts = AccountRepository(current_app.db_manager).find_all()
    return render_template(
        "fragments/account_list.html",
        accounts=all_accounts,
        flash_kind="success",
        flash_message="Account created.",
    )


@ui_bp.route("/categories")
def categories():
    all_categories = CategoryRepository(current_app.db_manager).find_all()
    return render_template("fragments/category_list.html", categories=all_categories)


@ui_bp.route("/imports/new")
def import_form():
    all_accounts = AccountRepository(current_app.db_manager).find_all()
    return render_template(
        "fragments/import_form.html",
        accounts=all_accounts,
        error=None,
        selected_account_id=None,
    )


def _hx_location_response(path: str):
    """Return an empty response that tells htmx to navigate to ``path``.

    Uses the ``HX-Location`` header (client-side navigation) rather than
    ``HX-Redirect`` (full page reload) so the app shell stays intact and the
    fragment is swapped into ``#content``.
    """
    resp = make_response("", 200)
    resp.headers["HX-Location"] = json.dumps({"path": path, "target": "#content"})
    return resp


@ui_bp.route("/imports")
def imports_list():
    db = current_app.db_manager
    imports = DataImportRepository(db).find_all()
    account_names = {a.id: a.name for a in AccountRepository(db).find_all()}
    transactions_repo = TransactionRepository(db)

    rows = []
    for imp in imports:
        total = transactions_repo.count_by_data_import(imp.id)
        unreviewed = transactions_repo.count_unreviewed(imp.id)
        rows.append(
            {
                "import": imp,
                "account_name": account_names.get(imp.account_id, "—"),
                "total": total,
                "reviewed": total - unreviewed,
                "unreviewed": unreviewed,
            }
        )

    return render_template("fragments/import_list.html", rows=rows)


@ui_bp.route("/imports", methods=["POST"])
def import_upload():
    from services.ingestion import IngestionService

    accounts_repo = AccountRepository(current_app.db_manager)

    # Validate account_id
    account_id_str = request.form.get("account_id", "").strip()
    try:
        account_id = int(account_id_str)
    except ValueError:
        all_accounts = accounts_repo.find_all()
        return (
            render_template(
                "fragments/import_form.html",
                accounts=all_accounts,
                error="Please select an account.",
                selected_account_id=None,
            ),
            400,
        )

    account = accounts_repo.find(account_id)
    if account is None:
        all_accounts = accounts_repo.find_all()
        return (
            render_template(
                "fragments/import_form.html",
                accounts=all_accounts,
                error="Account not found.",
                selected_account_id=None,
            ),
            404,
        )

    # Validate file upload
    file = request.files.get("csv_file")
    if not file or not file.filename:
        all_accounts = accounts_repo.find_all()
        return (
            render_template(
                "fragments/import_form.html",
                accounts=all_accounts,
                error="Please select a CSV file.",
                selected_account_id=account_id,
            ),
            400,
        )

    # Save to temp directory and ingest
    config = current_app.config["NECKER_CONFIG"]
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / file.filename
        file.save(str(csv_path))

        try:
            result = IngestionService(current_app.db_manager, config).ingest_csv(
                csv_path, account
            )
        except ValueError as e:
            all_accounts = accounts_repo.find_all()
            return (
                render_template(
                    "fragments/import_form.html",
                    accounts=all_accounts,
                    error=str(e),
                    selected_account_id=account_id,
                ),
                400,
            )
        except Exception:
            all_accounts = accounts_repo.find_all()
            return (
                render_template(
                    "fragments/import_form.html",
                    accounts=all_accounts,
                    error="An unexpected error occurred during import. Please try again.",
                    selected_account_id=account_id,
                ),
                500,
            )

    # If no new transactions, skip review entirely.
    if result["parsed"] == 0 or result["inserted"] == 0:
        return render_template(
            "fragments/import_success.html",
            result=result,
            account=account,
            transactions_url=None,
            month_str=None,
            mode="upload",
        )

    # New transactions landed — hand off to the batched review flow.
    return _hx_location_response(f"/ui/imports/{result['data_import_id']}/review")


@ui_bp.route("/imports/<int:data_import_id>/review")
def import_review_next(data_import_id):
    """Load (and auto-categorize) the next unreviewed batch for an import."""
    db = current_app.db_manager
    data_import = DataImportRepository(db).find(data_import_id)
    if data_import is None:
        all_accounts = AccountRepository(db).find_all()
        return (
            render_template(
                "fragments/import_form.html",
                accounts=all_accounts,
                error="Import not found.",
                selected_account_id=None,
            ),
            404,
        )

    transactions_repo = TransactionRepository(db)
    total = transactions_repo.count_by_data_import(data_import_id)
    unreviewed = transactions_repo.count_unreviewed(data_import_id)
    account = AccountRepository(db).find(data_import.account_id)

    # Nothing left to review — show the completion view.
    if unreviewed == 0:
        transactions_url = None
        month_str = None
        if total > 0:
            txns = transactions_repo.find_by_data_import_id(data_import_id)
            earliest = min(t.transaction_date for t in txns)
            month_str = f"{earliest.year:04d}/{earliest.month:02d}"
            transactions_url = f"/ui/transactions?month={month_str}"
        return render_template(
            "fragments/import_success.html",
            result=None,
            account=account,
            transactions_url=transactions_url,
            month_str=month_str,
            mode="review-complete",
        )

    config = current_app.config["NECKER_CONFIG"]
    from services.categorization import auto_categorize_for_import_batch

    load = auto_categorize_for_import_batch(
        db, config, data_import_id, config.llm_categorization_batch_size
    )

    all_categories = CategoryRepository(db).find_all()
    categories_map = {c.id: c.name for c in all_categories}

    return render_template(
        "fragments/import_review.html",
        transactions=load.transactions,
        account=account,
        categories=all_categories,
        categories_map=categories_map,
        result=None,
        data_import_id=data_import_id,
        total=total,
        reviewed=total - unreviewed,
        remaining=unreviewed,
        llm_failed=load.llm_failed,
        edits={},
        row_errors={},
    )


@ui_bp.route("/imports/<int:data_import_id>/review", methods=["POST"])
def import_review(data_import_id):
    db = current_app.db_manager
    transactions_repo = TransactionRepository(db)

    data_import = DataImportRepository(db).find(data_import_id)
    if data_import is None:
        all_accounts = AccountRepository(db).find_all()
        return (
            render_template(
                "fragments/import_form.html",
                accounts=all_accounts,
                error="Import not found.",
                selected_account_id=None,
            ),
            404,
        )

    all_categories = CategoryRepository(db).find_all()
    valid_category_ids = {c.id for c in all_categories}
    categories_map = {c.id: c.name for c in all_categories}

    # The submitted form determines which transactions are in this batch.
    submitted_ids = [
        key[len("category_id_") :]
        for key in request.form
        if key.startswith("category_id_")
    ]
    batch = []
    for txn_id in submitted_ids:
        txn = transactions_repo.find(txn_id)
        if txn is not None and txn.data_import_id == data_import_id:
            batch.append(txn)
    batch.sort(key=lambda t: (t.transaction_date, t.id))

    # Parse and validate the submitted edits.
    edits = {}
    row_errors = {}
    for txn in batch:
        cat_val = request.form.get(f"category_id_{txn.id}", "").strip()
        merchant_val = request.form.get(f"merchant_name_{txn.id}", "").strip()
        edits[txn.id] = {"category_id": cat_val, "merchant_name": merchant_val}

        if cat_val:
            try:
                cat_id = int(cat_val)
                if cat_id not in valid_category_ids:
                    row_errors.setdefault(txn.id, {})["category"] = (
                        "Invalid category selected."
                    )
            except ValueError:
                row_errors.setdefault(txn.id, {})["category"] = "Invalid category."

    if row_errors:
        total = transactions_repo.count_by_data_import(data_import_id)
        unreviewed = transactions_repo.count_unreviewed(data_import_id)
        account = AccountRepository(db).find(data_import.account_id)
        return (
            render_template(
                "fragments/import_review.html",
                transactions=batch,
                account=account,
                categories=all_categories,
                categories_map=categories_map,
                result=None,
                data_import_id=data_import_id,
                total=total,
                reviewed=total - unreviewed,
                remaining=unreviewed,
                llm_failed=False,
                edits=edits,
                row_errors=row_errors,
            ),
            400,
        )

    # Apply edits and mark the batch reviewed, then advance to the next batch.
    for txn in batch:
        edit = edits[txn.id]
        txn.category_id = int(edit["category_id"]) if edit["category_id"] else None
        txn.merchant_name = edit["merchant_name"] or None
        txn.import_reviewed = True

    if batch:
        transactions_repo.batch_update(
            batch, ["category_id", "merchant_name", "import_reviewed"]
        )

    return _hx_location_response(f"/ui/imports/{data_import_id}/review")


# --- Budgets ---


@ui_bp.route("/budgets")
def budgets():
    all_budgets = BudgetRepository(current_app.db_manager).find_all()
    return render_template(
        "fragments/budget_list.html", budgets=all_budgets, error=None
    )


@ui_bp.route("/budgets/new")
def budget_new():
    all_categories = CategoryRepository(current_app.db_manager).find_all()
    return render_template(
        "fragments/budget_form.html",
        categories=all_categories,
        error=None,
        form_data={},
    )


@ui_bp.route("/budgets", methods=["POST"])
def budget_create():
    category_id_str = request.form.get("category_id", "").strip()
    period_type = request.form.get("period_type", "").strip()
    amount_str = request.form.get("amount", "").strip()
    form_data = {
        "category_id": category_id_str,
        "period_type": period_type,
        "amount": amount_str,
    }
    all_categories = CategoryRepository(current_app.db_manager).find_all()

    try:
        category_id = int(category_id_str)
    except ValueError:
        return (
            render_template(
                "fragments/budget_form.html",
                categories=all_categories,
                error="Please select a category.",
                form_data=form_data,
            ),
            400,
        )

    if period_type not in ("monthly", "yearly"):
        return (
            render_template(
                "fragments/budget_form.html",
                categories=all_categories,
                error="Period type must be 'monthly' or 'yearly'.",
                form_data=form_data,
            ),
            400,
        )

    try:
        amount_dollars = float(amount_str)
        amount_cents = int(round(amount_dollars * 100))
    except ValueError:
        return (
            render_template(
                "fragments/budget_form.html",
                categories=all_categories,
                error="Amount must be a number.",
                form_data=form_data,
            ),
            400,
        )

    if amount_cents <= 0:
        return (
            render_template(
                "fragments/budget_form.html",
                categories=all_categories,
                error="Amount must be greater than zero.",
                form_data=form_data,
            ),
            400,
        )

    try:
        BudgetRepository(current_app.db_manager).create(
            category_id, period_type, amount_cents
        )
    except sqlite3.IntegrityError:
        return (
            render_template(
                "fragments/budget_form.html",
                categories=all_categories,
                error="A budget for this category and period already exists.",
                form_data=form_data,
            ),
            400,
        )

    all_budgets = BudgetRepository(current_app.db_manager).find_all()
    return render_template(
        "fragments/budget_list.html",
        budgets=all_budgets,
        error=None,
        flash_kind="success",
        flash_message="Budget created.",
    )


@ui_bp.route("/budgets/<int:budget_id>", methods=["DELETE"])
def budget_delete(budget_id):
    BudgetRepository(current_app.db_manager).delete(budget_id)
    return "", 200


@ui_bp.route("/budgets/<int:budget_id>/edit")
def budget_edit(budget_id):
    budget = BudgetRepository(current_app.db_manager).find(budget_id)
    if budget is None:
        return "", 404
    return render_template("fragments/budget_amount_edit.html", budget=budget)


@ui_bp.route("/budgets/<int:budget_id>/amount")
def budget_amount(budget_id):
    budget = BudgetRepository(current_app.db_manager).find(budget_id)
    if budget is None:
        return "", 404
    return render_template("fragments/budget_amount_display.html", budget=budget)


@ui_bp.route("/budgets/<int:budget_id>", methods=["PATCH"])
def budget_update(budget_id):
    budgets_repo = BudgetRepository(current_app.db_manager)
    amount_str = request.form.get("amount", "").strip()

    try:
        amount_dollars = float(amount_str)
        amount_cents = int(round(amount_dollars * 100))
    except ValueError:
        budget = budgets_repo.find(budget_id)
        return render_template("fragments/budget_amount_edit.html", budget=budget), 400

    if amount_cents <= 0:
        budget = budgets_repo.find(budget_id)
        return render_template("fragments/budget_amount_edit.html", budget=budget), 400

    budget = budgets_repo.update_amount(budget_id, amount_cents)
    if budget is None:
        return "", 404

    return render_template("fragments/budget_amount_display.html", budget=budget)


# --- Reports ---


VALID_BASES = ("cash", "accrual")


def _report_request_params():
    """Parse ?month=YYYY/MM&basis=cash|accrual. Defaults to current month + cash.

    Returns (year, month, basis, error_message). error_message is None on success.
    """
    month_raw = request.args.get("month")
    basis = request.args.get("basis", "cash")

    if basis not in VALID_BASES:
        return None, None, basis, f"basis must be one of: {', '.join(VALID_BASES)}"

    if month_raw:
        try:
            year, month = _parse_month(month_raw)
        except (ValueError, AttributeError):
            return (
                None,
                None,
                basis,
                f"Invalid month format '{month_raw}'. Use YYYY/MM.",
            )
    else:
        today = date.today()
        year, month = today.year, today.month

    return year, month, basis, None


@ui_bp.route("/reports/transactions")
def report_transactions():
    year, month, basis, error = _report_request_params()
    if error:
        return render_template(
            "fragments/report_transactions.html",
            error=error,
            report=None,
            categories={},
            month_label=None,
            basis=basis,
            prev_month=None,
            next_month=None,
        ), 400

    report = MonthTransactionsReport(current_app.db_manager).run(year, month, basis)

    all_categories = CategoryRepository(current_app.db_manager).find_all()
    categories = {c.id: c.name for c in all_categories}

    month_label = f"{year:04d}/{month:02d}"
    prev_year, prev_month, next_year, next_month = _adjacent_months(year, month)

    return render_template(
        "fragments/report_transactions.html",
        error=None,
        report=report,
        categories=categories,
        month_label=month_label,
        basis=basis,
        prev_month=f"{prev_year:04d}/{prev_month:02d}",
        next_month=f"{next_year:04d}/{next_month:02d}",
    )


@ui_bp.route("/reports/spending-summary")
def report_spending_summary():
    year, month, basis, error = _report_request_params()
    if error:
        return render_template(
            "fragments/report_spending_summary.html",
            error=error,
            summary=None,
            categories={},
            month_label=None,
            basis=basis,
            prev_month=None,
            next_month=None,
        ), 400

    if basis == "cash":
        summary = CashSpendingSummaryReport(current_app.db_manager).run(year, month)
    else:
        summary = AccrualSpendingSummaryReport(current_app.db_manager).run(year, month)

    all_categories = CategoryRepository(current_app.db_manager).find_all()
    categories = {c.id: c.name for c in all_categories}

    month_label = f"{year:04d}/{month:02d}"
    prev_year, prev_month, next_year, next_month = _adjacent_months(year, month)

    return render_template(
        "fragments/report_spending_summary.html",
        error=None,
        summary=summary,
        categories=categories,
        month_label=month_label,
        basis=basis,
        prev_month=f"{prev_year:04d}/{prev_month:02d}",
        next_month=f"{next_year:04d}/{next_month:02d}",
    )
