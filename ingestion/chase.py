import csv
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, TextIO

from models.transaction import Transaction

logger = logging.getLogger(__name__)


def ingest(source: TextIO, account_id: int) -> List[Transaction]:
    """
    Ingest Chase Credit Card CSV transactions.

    Expected format:
    - Header row (line 1): Transaction Date,Post Date,Description,Category,Type,Amount,Memo
    - Transaction rows (line 2+): actual transaction data
    """
    transactions = []
    reader = csv.reader(source)

    # Read and validate header
    try:
        header = next(reader)
        if len(header) < 6 or header[0] != "Transaction Date":
            logger.error(f"Invalid header format: {header}")
            return transactions
        logger.info("Found Chase CSV header")
    except StopIteration:
        logger.error("Empty CSV file")
        return transactions

    # Process transaction rows
    line_num = 1
    for row in reader:
        line_num += 1

        if not row or len(row) < 6:
            logger.warning(f"Skipping malformed line {line_num}: {row}")
            continue

        try:
            raw_line = ",".join(row)
            trans_date_str = row[0].strip()
            post_date_str = row[1].strip()
            description = row[2].strip().strip('"')
            category = row[3].strip().strip('"')
            type_field = row[4].strip()
            amount_str = row[5].strip()
            memo = row[6].strip().strip('"') if len(row) > 6 else ""

            # Skip rows with missing critical data
            if not trans_date_str or not amount_str:
                logger.warning(
                    f"Skipping line {line_num} with missing date/amount: {row}"
                )
                continue

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

            transaction = Transaction.create_with_checksum(
                raw_data=raw_line,
                account_id=account_id,
                transaction_date=transaction_date,
                post_date=post_date,
                description=description,
                category=category if category else None,
                amount=amount,
                type=transaction_type,
                additional_metadata=additional_metadata
                if additional_metadata
                else None,
            )

            transactions.append(transaction)

        except Exception as e:
            logger.error(f"Error processing line {line_num}: {row} - {e}")
            continue

    logger.info(f"Successfully ingested {len(transactions)} transactions")
    return transactions
