from dataclasses import dataclass
from datetime import date
from typing import Optional
import hashlib


@dataclass
class Transaction:
    id: str  # checksum of raw transaction data
    account_id: int
    transaction_date: date
    post_date: Optional[date]
    description: str
    bank_category: Optional[str]  # category from bank/CSV import
    amount: int  # always positive, stored in cents (e.g. $5.75 → 575)
    transaction_type: str  # 'income', 'expense', or 'transfer'
    additional_metadata: Optional[dict] = None
    data_import_id: int = (
        0  # reference to the data import operation (set during ingestion)
    )
    category_id: Optional[int] = None  # user-defined category
    auto_category_id: Optional[int] = None  # LLM-suggested category
    merchant_name: Optional[str] = None  # user-defined merchant name
    auto_merchant_name: Optional[str] = None  # LLM-suggested merchant name
    amortize_months: Optional[int] = None  # number of months to amortize over
    amortize_end_date: Optional[date] = None  # calculated end date for amortization
    accrued: bool = (
        False  # runtime-only flag indicating this is a virtual accrued transaction
    )

    @classmethod
    def create_with_checksum(
        cls,
        raw_data: str,
        account_id: int,
        transaction_date: date,
        post_date: Optional[date],
        description: str,
        bank_category: Optional[str],
        amount: int,
        transaction_type: str,
        additional_metadata: Optional[dict] = None,
    ) -> "Transaction":
        """Create a Transaction with auto-generated checksum ID.

        The ID is sha256(raw_data), where raw_data is the raw CSV row string.
        This provides idempotent deduplication: re-importing the same CSV row
        produces the same ID, so INSERT OR IGNORE in bulk_create safely skips it.

        Trade-off: two genuinely different real-world transactions that happen to
        produce identical CSV rows (same date, description, and amount) will share
        an ID and the second will be silently dropped on insert. bulk_create logs a
        warning when it detects this within a single import batch.
        """
        transaction_id = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()
        return cls(
            id=transaction_id,
            account_id=account_id,
            transaction_date=transaction_date,
            post_date=post_date,
            description=description,
            bank_category=bank_category,
            amount=amount,
            transaction_type=transaction_type,
            additional_metadata=additional_metadata,
        )
