import csv
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, TextIO

from models.transaction import Transaction

logger = logging.getLogger(__name__)


def ingest(source: TextIO, account_id: int) -> List[Transaction]:
    """
    Ingest Discover Card CSV transactions.

    Expected format:
    - Header row (line 1): Trans. Date,Post Date,Description,Amount,Category
    - Transaction rows (line 2+): actual transaction data
    """
    transactions = []
    reader = csv.reader(source)

    # Read and validate header
    try:
        header = next(reader)
        if len(header) < 5 or header[0] != "Trans. Date":
            logger.error(f"Invalid header format: {header}")
            return transactions
        logger.info("Found Discover CSV header")
    except StopIteration:
        logger.error("Empty CSV file")
        return transactions

    # Process transaction rows
    line_num = 1
    for row in reader:
        line_num += 1

        if not row or len(row) < 5:
            logger.warning(f"Skipping malformed line {line_num}: {row}")
            continue

        try:
            raw_line = ",".join(row)
            trans_date_str = row[0].strip()
            post_date_str = row[1].strip()
            description = row[2].strip().strip('"')
            amount_str = row[3].strip()
            category = row[4].strip().strip('"')

            # Skip rows with missing critical data
            if not trans_date_str or not amount_str:
                logger.warning(
                    f"Skipping line {line_num} with missing date/amount: {row}"
                )
                continue

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

            transaction = Transaction.create_with_checksum(
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

            transactions.append(transaction)

        except Exception as e:
            logger.error(f"Error processing line {line_num}: {row} - {e}")
            continue

    logger.info(f"Successfully ingested {len(transactions)} transactions")
    return transactions
