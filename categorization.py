"""Auto-categorization module using LLM for transaction categorization.

This module provides functionality to automatically categorize transactions
using a Large Language Model (LLM). The LLM learns from historical manually-
categorized transactions and suggests categories for new transactions.

Supports multiple LLM providers (OpenAI, Ollama) configured via the application config.
"""

from typing import List, Optional
from models.transaction import Transaction
from models.category import Category
from config import Config
from llm import get_llm_provider
from logger import get_logger

logger = get_logger()


def auto_categorize(
    transactions: List[Transaction],
    categories: List[Category],
    historical_transactions: List[Transaction],
    config: Optional[Config] = None,
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
        config: Optional config object. If None, LLM categorization is skipped.

    Returns:
        The same list of transactions with auto_category_id set to the
        suggested category ID, or None if categorization failed or confidence
        was too low.
    """
    logger.info(
        f"Auto-categorization called with {len(transactions)} transactions, "
        f"{len(categories)} categories, "
        f"{len(historical_transactions)} historical examples"
    )

    # Check if we have a config and LLM is enabled
    if config is None:
        logger.info("No config provided - skipping LLM categorization")
        return transactions

    # Get LLM provider from config
    try:
        provider = get_llm_provider(config)
    except Exception as e:
        logger.error(f"Failed to initialize LLM provider: {e}")
        return transactions

    if provider is None:
        logger.info("LLM categorization disabled - skipping")
        return transactions

    # Check if we have categories to work with
    if not categories:
        logger.warning("No categories available - cannot categorize transactions")
        return transactions

    # Call LLM provider to categorize
    try:
        suggestions = provider.categorize_transactions(
            transactions, categories, historical_transactions
        )

        # Create lookup map of transaction_id -> category_id
        suggestion_map = {s.transaction_id: s.category_id for s in suggestions}

        # Update transactions with auto_category_id
        for txn in transactions:
            if txn.id in suggestion_map:
                txn.auto_category_id = suggestion_map[txn.id]
                if txn.auto_category_id is not None:
                    logger.debug(
                        f"Transaction {txn.id[:8]}... auto-categorized as {txn.auto_category_id}"
                    )

        categorized_count = sum(
            1 for txn in transactions if txn.auto_category_id is not None
        )
        logger.info(
            f"Successfully auto-categorized {categorized_count}/{len(transactions)} transactions"
        )

    except Exception as e:
        logger.error(f"LLM categorization failed: {e}")
        # Return transactions unchanged on error
        return transactions

    return transactions
