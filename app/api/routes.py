"""API route definitions — read-only JSON endpoints."""

from datetime import date

from flask import jsonify, request, current_app

from app.api import api_bp
from services import analysis


def _transaction_to_dict(t) -> dict:
    return {
        "id": t.id,
        "account_id": t.account_id,
        "data_import_id": t.data_import_id,
        "transaction_date": t.transaction_date.isoformat(),
        "post_date": t.post_date.isoformat() if t.post_date else None,
        "description": t.description,
        "bank_category": t.bank_category,
        "category_id": t.category_id,
        "auto_category_id": t.auto_category_id,
        "merchant_name": t.merchant_name,
        "auto_merchant_name": t.auto_merchant_name,
        "amount": t.amount,
        "transaction_type": t.transaction_type,
        "amortize_months": t.amortize_months,
        "amortize_end_date": (
            t.amortize_end_date.isoformat() if t.amortize_end_date else None
        ),
        "accrued": t.accrued,
    }


def _category_to_dict(c) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "parent_id": c.parent_id,
    }


def _parse_month(value: str, param_name: str):
    """Parse a YYYY/MM string into (year, month). Returns (None, error_response) on failure."""
    try:
        year_str, month_str = value.split("/")
        year = int(year_str)
        month = int(month_str)
        if not (1 <= month <= 12):
            raise ValueError
        return (year, month), None
    except (ValueError, AttributeError):
        return None, (
            jsonify(
                {
                    "error": "bad_request",
                    "message": f"'{param_name}' must be in YYYY/MM format",
                }
            ),
            400,
        )


# --- Accounts ---


@api_bp.route("/accounts")
def list_accounts():
    accounts = current_app.services.accounts.find_all()
    return jsonify([a.to_dict() for a in accounts])


@api_bp.route("/accounts/<int:account_id>")
def get_account(account_id):
    account = current_app.services.accounts.find(account_id)
    if account is None:
        return jsonify(
            {"error": "not_found", "message": f"Account {account_id} not found"}
        ), 404
    return jsonify(account.to_dict())


# --- Categories ---


@api_bp.route("/categories")
def list_categories():
    categories = current_app.services.categories.find_all()
    return jsonify([_category_to_dict(c) for c in categories])


# --- Transactions ---


@api_bp.route("/transactions/summary")
def get_transactions_summary():
    start_raw = request.args.get("start")
    end_raw = request.args.get("end")

    if not start_raw:
        return jsonify(
            {"error": "bad_request", "message": "'start' query parameter is required"}
        ), 400
    if not end_raw:
        return jsonify(
            {"error": "bad_request", "message": "'end' query parameter is required"}
        ), 400

    start_parsed, err = _parse_month(start_raw, "start")
    if err:
        return err
    start_year, start_month = start_parsed

    end_parsed, err = _parse_month(end_raw, "end")
    if err:
        return err
    end_year, end_month = end_parsed

    start_date = date(start_year, start_month, 1)
    end_date = date(end_year, end_month, 1)

    if end_date < start_date:
        return jsonify(
            {"error": "bad_request", "message": "'end' must not be before 'start'"}
        ), 400

    summary = analysis.get_period_summary(current_app.services, start_date, end_date)

    # Serialize: expenses_by_category keys are ints; convert to str for JSON compatibility
    def _serialize_basis(basis_data):
        result = {}
        for month_key, month_summary in basis_data.items():
            result[month_key] = {
                "income_total": month_summary["income_total"],
                "expense_total": month_summary["expense_total"],
                "net": month_summary["net"],
                "expenses_by_category": {
                    str(k): v for k, v in month_summary["expenses_by_category"].items()
                },
            }
        return result

    return jsonify(
        {
            "cash_basis": _serialize_basis(summary["cash_basis"]),
            "accrual_basis": _serialize_basis(summary["accrual_basis"]),
        }
    )


@api_bp.route("/transactions")
def list_transactions():
    month_raw = request.args.get("month")
    if not month_raw:
        return jsonify(
            {"error": "bad_request", "message": "'month' query parameter is required"}
        ), 400

    month_parsed, err = _parse_month(month_raw, "month")
    if err:
        return err
    year, month = month_parsed

    transactions = current_app.services.transactions.get_transactions_by_month(
        year, month
    )
    return jsonify([_transaction_to_dict(t) for t in transactions])


@api_bp.route("/transactions/<transaction_id>")
def get_transaction(transaction_id):
    transaction = current_app.services.transactions.find(transaction_id)
    if transaction is None:
        return jsonify(
            {
                "error": "not_found",
                "message": f"Transaction {transaction_id!r} not found",
            }
        ), 404
    return jsonify(_transaction_to_dict(transaction))
