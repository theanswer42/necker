"""Typed output models for the reports layer."""

from dataclasses import dataclass, field
from typing import Dict, List

from models.transaction import Transaction


@dataclass
class MonthTransactions:
    year: int
    month: int
    basis: str  # "cash" or "accrual"
    transactions: List[Transaction]


@dataclass
class MonthSpendingSummary:
    year: int
    month: int
    basis: str  # "cash" or "accrual"
    income_total: int  # cents
    expense_total: int  # cents
    net: int  # cents (income - expenses)
    expenses_by_category: Dict[int, int] = field(default_factory=dict)
