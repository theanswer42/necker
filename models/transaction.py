from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional
import hashlib
import json


@dataclass
class Transaction:
    id: str  # checksum of raw transaction data
    account_id: int
    transaction_date: date
    post_date: Optional[date]
    description: str
    category: Optional[str]
    amount: Decimal  # always positive
    type: str  # 'income', 'expense', or 'transfer'
    additional_metadata: Optional[dict] = None

    @classmethod
    def create_with_checksum(
        cls,
        raw_data: str,
        account_id: int,
        transaction_date: date,
        post_date: Optional[date],
        description: str,
        category: Optional[str],
        amount: Decimal,
        type: str,
        additional_metadata: Optional[dict] = None,
    ) -> "Transaction":
        """Create a Transaction with auto-generated checksum ID."""
        transaction_id = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()
        return cls(
            id=transaction_id,
            account_id=account_id,
            transaction_date=transaction_date,
            post_date=post_date,
            description=description,
            category=category,
            amount=amount,
            type=type,
            additional_metadata=additional_metadata,
        )

    def to_dict(self) -> dict:
        """Convert transaction to dictionary for database storage."""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "transaction_date": self.transaction_date.isoformat(),
            "post_date": self.post_date.isoformat() if self.post_date else None,
            "description": self.description,
            "category": self.category,
            "amount": float(self.amount),
            "transaction_type": self.type,
            "raw_data": None,  # Will be set by ingestion module
            "additional_metadata": (
                json.dumps(self.additional_metadata)
                if self.additional_metadata
                else None
            ),
        }
