import csv
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, TextIO

from models.transaction import Transaction

logger = logging.getLogger(__name__)

_CSV_HEADERS = [
    "Transaction Date",
    "Post Date",
    "Description",
    "Category",
    "Type",
    "Amount",
    "Memo",
]


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
    category = row[3].strip().strip('"')
    type_field = row[4].strip()
    amount_str = row[5].strip()
    memo = row[6].strip().strip('"') if len(row) > 6 else ""

    # Validate required fields
    if not trans_date_str or not amount_str:
        raise ValueError(
            f"Missing required fields: transaction_date='{trans_date_str}', amount='{amount_str}'"
        )

    # Parse dates
    transaction_date = datetime.strptime(trans_date_str, "%m/%d/%Y").date()
    post_date = datetime.strptime(post_date_str, "%m/%d/%Y").date()

    # Parse amount
    amount_value = Decimal(amount_str.replace(",", ""))
    amount = abs(amount_value)

    # Build additional metadata
    additional_metadata = {}
    if memo:
        additional_metadata["memo"] = memo

    # Determine transaction type
    # Chase credit card: negative = charge/expense, positive = payment
    if type_field == "Payment" or "AUTOMATIC PAYMENT" in description.upper():
        transaction_type = "transfer"
    elif amount_value < 0:
        transaction_type = "expense"
    else:
        transaction_type = "income"

    return Transaction.create_with_checksum(
        raw_data=raw_line,
        account_id=account_id,
        transaction_date=transaction_date,
        post_date=post_date,
        description=description,
        category=category if category else None,
        amount=amount,
        type=transaction_type,
        additional_metadata=additional_metadata if additional_metadata else None,
    )


def ingest(source: TextIO, account_id: int) -> List[Transaction]:
    """
    Ingest Chase Credit Card CSV transactions.

    Expected format:
    - Header row (line 1): Transaction Date,Post Date,Description,Category,Type,Amount,Memo
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

    logger.info("Validated Chase CSV header")

    # Process transaction rows
    line_num = 1
    for row in reader:
        line_num += 1

        if not row or len(row) < 6:
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
