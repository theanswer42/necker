"""Auto-categorization module using LLM for transaction categorization.

This module provides functionality to automatically categorize transactions
using a Large Language Model (LLM). The LLM learns from historical manually-
categorized transactions and suggests categories for new transactions.

Future implementation will support multiple LLM providers (OpenAI, Claude, Ollama)
configured via the application config.
"""

from typing import List
from models.transaction import Transaction
from models.category import Category
from logger import get_logger

logger = get_logger()


def auto_categorize(
    transactions: List[Transaction],
    categories: List[Category],
    historical_transactions: List[Transaction],
) -> List[Transaction]:
    """Automatically categorize transactions using an LLM.

    This function takes a list of uncategorized transactions and suggests
    categories based on historical patterns learned from manually-categorized
    transactions.

    The LLM is given:
    - A list of available categories
    - Historical transactions with their manual categories (training examples)
    - New transactions to categorize

    It returns the same transactions with auto_category_id populated.

    Args:
        transactions: List of newly imported transactions to categorize.
        categories: List of all available user-defined categories.
        historical_transactions: List of previously categorized transactions
                                from the same account (last 90 days) to use
                                as training examples.

    Returns:
        The same list of transactions with auto_category_id set to the
        suggested category ID, or None if categorization failed or confidence
        was too low.

    Future Implementation:
        - Configure LLM provider (OpenAI, Claude, Ollama) via config
        - Return confidence scores with suggestions
        - Handle API failures gracefully
        - Batch categorization for efficiency
        - Cache identical transaction descriptions

    Note:
        This is currently a stub implementation that returns transactions
        unchanged (auto_category_id remains None). The actual LLM integration
        will be implemented in a future iteration.
    """
    logger.info(
        f"Auto-categorization called with {len(transactions)} transactions, "
        f"{len(categories)} categories, "
        f"{len(historical_transactions)} historical examples"
    )

    # TODO: Implement LLM-based categorization
    # For now, return transactions unchanged
    logger.info(
        "Auto-categorization not yet implemented - transactions returned unchanged"
    )

    return transactions
