"""UI route definitions — server-rendered HTML fragments for htmx."""

import tempfile
from datetime import date
from pathlib import Path

from flask import render_template, request, current_app

from app.ui import ui_bp


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

    txns = current_app.services.transactions.get_transactions_by_month(year, month)

    # Build category lookup for display
    all_categories = current_app.services.categories.find_all()
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
    all_accounts = current_app.services.accounts.find_all()
    return render_template("fragments/account_list.html", accounts=all_accounts)


@ui_bp.route("/categories")
def categories():
    all_categories = current_app.services.categories.find_all()
    return render_template("fragments/category_list.html", categories=all_categories)


@ui_bp.route("/imports/new")
def import_form():
    all_accounts = current_app.services.accounts.find_all()
    return render_template(
        "fragments/import_form.html",
        accounts=all_accounts,
        error=None,
        selected_account_id=None,
    )


@ui_bp.route("/imports", methods=["POST"])
def import_upload():
    from services.ingestion import ingest_csv

    # Validate account_id
    account_id_str = request.form.get("account_id", "").strip()
    try:
        account_id = int(account_id_str)
    except ValueError:
        all_accounts = current_app.services.accounts.find_all()
        return (
            render_template(
                "fragments/import_form.html",
                accounts=all_accounts,
                error="Please select an account.",
                selected_account_id=None,
            ),
            400,
        )

    account = current_app.services.accounts.find(account_id)
    if account is None:
        all_accounts = current_app.services.accounts.find_all()
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
        all_accounts = current_app.services.accounts.find_all()
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
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / file.filename
        file.save(str(csv_path))

        try:
            result = ingest_csv(csv_path, account, current_app.services)
        except ValueError as e:
            all_accounts = current_app.services.accounts.find_all()
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
            all_accounts = current_app.services.accounts.find_all()
            return (
                render_template(
                    "fragments/import_form.html",
                    accounts=all_accounts,
                    error="An unexpected error occurred during import. Please try again.",
                    selected_account_id=account_id,
                ),
                500,
            )

    # If no new transactions, skip review
    if result["parsed"] == 0 or result["inserted"] == 0:
        return render_template(
            "fragments/import_success.html",
            result=result,
            account=account,
            transactions_url=None,
            month_str=None,
            mode="upload",
        )

    # Fetch just-imported transactions for review
    transactions = current_app.services.transactions.find_by_data_import_id(
        result["data_import_id"]
    )
    all_categories = current_app.services.categories.find_all()
    categories_map = {c.id: c.name for c in all_categories}

    return render_template(
        "fragments/import_review.html",
        transactions=transactions,
        account=account,
        categories=all_categories,
        categories_map=categories_map,
        result=result,
        data_import_id=result["data_import_id"],
        edits={},
        row_errors={},
    )


@ui_bp.route("/imports/<int:data_import_id>/review", methods=["POST"])
def import_review(data_import_id):
    transactions = current_app.services.transactions.find_by_data_import_id(
        data_import_id
    )
    if not transactions:
        all_accounts = current_app.services.accounts.find_all()
        return (
            render_template(
                "fragments/import_form.html",
                accounts=all_accounts,
                error="No transactions found for this import.",
                selected_account_id=None,
            ),
            404,
        )

    all_categories = current_app.services.categories.find_all()
    valid_category_ids = {c.id for c in all_categories}
    categories_map = {c.id: c.name for c in all_categories}

    # Parse form data and validate
    edits = {}
    row_errors = {}

    for txn in transactions:
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
        account = current_app.services.accounts.find(transactions[0].account_id)
        return (
            render_template(
                "fragments/import_review.html",
                transactions=transactions,
                account=account,
                categories=all_categories,
                categories_map=categories_map,
                result=None,
                data_import_id=data_import_id,
                edits=edits,
                row_errors=row_errors,
            ),
            400,
        )

    # Apply edits to transaction objects and batch update
    for txn in transactions:
        edit = edits[txn.id]
        txn.category_id = int(edit["category_id"]) if edit["category_id"] else None
        txn.merchant_name = edit["merchant_name"] or None

    updated_count = current_app.services.transactions.batch_update(
        transactions, ["category_id", "merchant_name"]
    )

    earliest_date = min(t.transaction_date for t in transactions)
    month_str = f"{earliest_date.year:04d}/{earliest_date.month:02d}"

    return render_template(
        "fragments/import_success.html",
        result={"updated": updated_count},
        account=None,
        transactions_url=f"/ui/transactions?month={month_str}",
        month_str=month_str,
        mode="review",
    )
