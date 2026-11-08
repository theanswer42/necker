"""Base provider interface for LLM implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from models.category import Category
from models.transaction import Transaction


@dataclass
class CategorySuggestion:
    """Represents a category suggestion for a transaction."""

    transaction_id: str
    category_id: int | None
    merchant_name: str | None = None  # Detected merchant name
    confidence: float | None = None  # 0.0 to 1.0, if provider supports it
    reasoning: str | None = None  # Why this category was chosen


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Each provider can implement categorization in its own optimal way,
    using provider-specific features like structured outputs, thinking, etc.
    """

    @abstractmethod
    def categorize_transactions(
        self,
        transactions: list[Transaction],
        categories: list[Category],
        historical_transactions: list[Transaction],
    ) -> list[CategorySuggestion]:
        """Categorize a list of transactions using the LLM.

        Args:
            transactions: List of transactions to categorize.
            categories: List of available categories.
            historical_transactions: List of previously categorized transactions
                                    to use as examples.

        Returns:
            List of CategorySuggestion objects, one per transaction.
            If categorization fails or confidence is too low, category_id may be None.

        Raises:
            Exception: If LLM API call fails.
        """
