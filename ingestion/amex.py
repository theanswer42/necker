import csv
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, TextIO

from models.transaction import Transaction

logger = logging.getLogger(__name__)


def ingest(source: TextIO, account_id: int) -> List[Transaction]:
    """
    Ingest American Express CSV transactions.

    Expected format:
    - Header row (line 1): Date,Description,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
    - Transaction rows (line 2+): actual transaction data

    Note: Extended Details and other fields may contain newlines within quoted fields.
    """
    transactions = []
    reader = csv.reader(source)

    # Read and validate header
    try:
        header = next(reader)
        if len(header) < 11 or header[0] != "Date":
            logger.error(f"Invalid header format: {header}")
            return transactions
        logger.info("Found AMEX CSV header")
    except StopIteration:
        logger.error("Empty CSV file")
        return transactions

    # Process transaction rows
    line_num = 1
    for row in reader:
        line_num += 1

        if not row or len(row) < 3:
            logger.warning(f"Skipping malformed line {line_num}: {row}")
            continue

        try:
            raw_line = ",".join(row)
            date_str = row[0].strip()
            description = row[1].strip().strip('"')
            amount_str = row[2].strip()

            # Additional fields for metadata
            extended_details = row[3].strip().strip('"') if len(row) > 3 else ""
            appears_as = row[4].strip().strip('"') if len(row) > 4 else ""
            address = row[5].strip().strip('"') if len(row) > 5 else ""
            city_state = row[6].strip().strip('"') if len(row) > 6 else ""
            zip_code = row[7].strip().strip('"') if len(row) > 7 else ""
            country = row[8].strip().strip('"') if len(row) > 8 else ""
            reference = row[9].strip().strip('"').strip("'") if len(row) > 9 else ""
            category = row[10].strip().strip('"') if len(row) > 10 else ""

            # Skip rows with missing critical data
            if not date_str or not amount_str:
                logger.warning(
                    f"Skipping line {line_num} with missing date/amount: {row}"
                )
                continue

            # Parse date (AMEX has only one date field)
            transaction_date = datetime.strptime(date_str, "%m/%d/%Y").date()

            # Parse amount
            amount_value = Decimal(amount_str.replace(",", ""))
            amount = abs(amount_value)

            # Build additional metadata
            additional_metadata = {}
            if extended_details:
                additional_metadata["extended_details"] = extended_details
            if appears_as and appears_as != description:
                additional_metadata["appears_as"] = appears_as
            if address:
                additional_metadata["address"] = address
            if city_state:
                additional_metadata["city_state"] = city_state
            if zip_code:
                additional_metadata["zip_code"] = zip_code
            if country:
                additional_metadata["country"] = country
            if reference:
                additional_metadata["reference"] = reference

            # Determine transaction type
            # AMEX: positive = charge/expense, negative = payment
            if amount_value < 0 and "AUTOPAY PAYMENT" in description.upper():
                transaction_type = "transfer"
            elif amount_value < 0:
                transaction_type = "income"
            else:
                transaction_type = "expense"

            transaction = Transaction.create_with_checksum(
                raw_data=raw_line,
                account_id=account_id,
                transaction_date=transaction_date,
                post_date=None,  # AMEX CSV doesn't have separate post date
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
