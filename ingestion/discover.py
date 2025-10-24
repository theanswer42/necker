import csv
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, TextIO

from models.transaction import Transaction

logger = logging.getLogger(__name__)

_CSV_HEADERS = ["Trans. Date", "Post Date", "Description", "Amount", "Category"]


def row_to_transaction(row: List[str], account_id: int) -> Transaction:
    """Convert a CSV row to a Transaction object.

    Args:
        row: CSV row matching _CSV_HEADERS structure
        account_id: Account ID for this transaction

    Returns:
        Transaction object

    Raises:
        ValueError: If required fields are missing or invalid
    """
    raw_line = ",".join(row)
    trans_date_str = row[0].strip()
    post_date_str = row[1].strip()
    description = row[2].strip().strip('"')
    amount_str = row[3].strip()
    category = row[4].strip().strip('"')

    # Validate required fields
    if not trans_date_str or not amount_str:
        raise ValueError(
            f"Missing required fields: transaction_date='{trans_date_str}', amount='{amount_str}'"
        )

    # Parse dates
    transaction_date = datetime.strptime(trans_date_str, "%m/%d/%Y").date()
    post_date = datetime.strptime(post_date_str, "%m/%d/%Y").date()

    # Parse amount and determine type
    amount_value = Decimal(amount_str.replace(",", ""))
    amount = abs(amount_value)

    # Check for credit card payment transfers
    if category == "Payments and Credits" and description.startswith(
        "DIRECTPAY FULL BALANCE"
    ):
        transaction_type = "transfer"
    # Discover: positive = charge/expense, negative = payment/income
    elif amount_value < 0:
        transaction_type = "income"
    else:
        transaction_type = "expense"

    return Transaction.create_with_checksum(
        raw_data=raw_line,
        account_id=account_id,
        transaction_date=transaction_date,
        post_date=post_date,
        description=description,
        category=category if category else None,
        amount=amount,
        type=transaction_type,
        additional_metadata=None,
    )


def ingest(source: TextIO, account_id: int) -> List[Transaction]:
    """
    Ingest Discover Card CSV transactions.

    Expected format:
    - Header row (line 1): Trans. Date,Post Date,Description,Amount,Category
    - Transaction rows (line 2+): actual transaction data

    Raises:
        ValueError: If CSV headers don't match expected format
    """
    transactions = []
    reader = csv.reader(source)

    # Read and validate header
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("Empty CSV file")

    if header != _CSV_HEADERS:
        raise ValueError(
            f"CSV headers do not match expected format.\nExpected: {_CSV_HEADERS}\nGot: {header}"
        )

    logger.info("Validated Discover CSV header")

    # Process transaction rows
    line_num = 1
    for row in reader:
        line_num += 1

        if not row or len(row) < 5:
            logger.warning(f"Skipping malformed line {line_num}: {row}")
            continue

        try:
            transaction = row_to_transaction(row, account_id)
            transactions.append(transaction)
        except Exception as e:
            logger.error(f"Error processing line {line_num}: {row} - {e}")
            continue

    logger.info(f"Successfully ingested {len(transactions)} transactions")
    return transactions
