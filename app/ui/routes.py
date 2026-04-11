"""UI route definitions — server-rendered HTML fragments for htmx."""

from datetime import date

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
