import csv
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, TextIO

from models.transaction import Transaction

logger = logging.getLogger(__name__)


def ingest(source: TextIO, account_id: int) -> List[Transaction]:
    """
    Ingest Bank of America CSV transactions.

    Expected format:
    - Summary section (lines 1-5): ignored
    - Empty line (line 6): ignored
    - Header row (line 7): Date,Description,Amount,Running Bal.
    - Transaction rows (line 8+): actual transaction data
    """
    transactions = []
    reader = csv.reader(source)

    # Skip summary section and find the transaction header
    line_num = 0
    for row in reader:
        line_num += 1

        # Look for the transaction header row
        if len(row) >= 4 and row[0] == "Date" and row[1] == "Description":
            logger.info(f"Found transaction header at line {line_num}")
            break

    # Process transaction rows
    for row in reader:
        line_num += 1

        if not row or len(row) < 4:
            logger.warning(f"Skipping malformed line {line_num}: {row}")
            continue

        try:
            raw_line = ",".join(row)
            date_str = row[0].strip()
            description = row[1].strip().strip('"')
            amount_str = row[2].strip().strip('"')
            running_balance = row[3].strip().strip('"')

            # Skip rows that don't look like transactions
            if not date_str or not amount_str:
                logger.warning(
                    f"Skipping line {line_num} with missing date/amount: {row}"
                )
                continue

            # Parse date
            transaction_date = datetime.strptime(date_str, "%m/%d/%Y").date()

            # Parse amount and determine type
            if amount_str.startswith("-"):
                transaction_type = "debit"
                amount = Decimal(amount_str[1:].replace(",", ""))
            else:
                transaction_type = "credit"
                amount = Decimal(amount_str.replace(",", ""))

            # Create additional metadata
            additional_metadata = {"running_balance": running_balance}

            transaction = Transaction.create_with_checksum(
                raw_data=raw_line,
                account_id=account_id,
                transaction_date=transaction_date,
                post_date=None,  # BoFA CSV doesn't have separate post date
                description=description,
                category=None,  # BoFA CSV doesn't include category
                amount=amount,
                type=transaction_type,
                additional_metadata=additional_metadata,
            )

            transactions.append(transaction)

        except Exception as e:
            logger.error(f"Error processing line {line_num}: {row} - {e}")
            continue

    logger.info(f"Successfully ingested {len(transactions)} transactions")
    return transactions
