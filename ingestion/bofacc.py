import csv
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, TextIO

from models.transaction import Transaction

logger = logging.getLogger(__name__)

_CSV_HEADERS = ["Posted Date", "Reference Number", "Payee", "Address", "Amount"]


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
    posted_date_str = row[0].strip()
    reference_number = row[1].strip()
    payee = row[2].strip().strip('"')
    address = row[3].strip().strip('"')
    amount_str = row[4].strip()

    # Validate required fields
    if not posted_date_str or not amount_str:
        raise ValueError(
            f"Missing required fields: posted_date='{posted_date_str}', amount='{amount_str}'"
        )

    # Parse date
    transaction_date = datetime.strptime(posted_date_str, "%m/%d/%Y").date()

    # Parse amount
    amount_value = Decimal(amount_str.replace(",", ""))
    amount = abs(amount_value)

    # Create additional metadata
    additional_metadata = {
        "reference_number": reference_number,
        "address": address,
    }

    # Determine transaction type
    # BofA CC: negative = charge/expense, positive = payment
    if amount_value > 0:
        # Positive amount = payment
        transaction_type = "transfer"
    else:
        # Negative amount = charge
        transaction_type = "expense"

    return Transaction.create_with_checksum(
        raw_data=raw_line,
        account_id=account_id,
        transaction_date=transaction_date,
        post_date=None,  # BofA CC CSV doesn't have separate post date
        description=payee,
        bank_category=None,  # BofA CC CSV doesn't include category
        amount=amount,
        type=transaction_type,
        additional_metadata=additional_metadata,
    )


def ingest(source: TextIO, account_id: int) -> List[Transaction]:
    """
    Ingest Bank of America Credit Card CSV transactions.

    Expected format:
    - Header row (line 1): Posted Date,Reference Number,Payee,Address,Amount
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

    logger.info("Validated Bank of America Credit Card CSV header")

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
