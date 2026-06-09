"""Auto-categorization service using LLM for transaction categorization.

This module provides functionality to automatically categorize transactions
using a Large Language Model (LLM). The LLM learns from historical manually-
categorized transactions and suggests categories for new transactions.

Supports multiple LLM providers (OpenAI, Ollama) configured via the application config.
"""

from typing import List, NamedTuple, Optional
from models.transaction import Transaction
from models.category import Category
from config import Config
from llm import get_llm_provider
from logger import get_logger

logger = get_logger()


class ImportBatchLoad(NamedTuple):
    """Result of loading + categorizing the next review batch for an import.

    Attributes:
        transactions: The batch's transactions (re-fetched after persistence),
            empty if no unreviewed transactions remain.
        llm_failed: True if auto-categorization was attempted for this batch
            but the LLM provider could not be used (e.g. misconfiguration).
            Drives the "auto-categorization unavailable" banner. False when the
            LLM is simply disabled or no categorization was needed.
    """

    transactions: List[Transaction]
    llm_failed: bool


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

        # Create lookup maps for category_id and merchant_name
        suggestion_map = {s.transaction_id: s for s in suggestions}

        # Update transactions with auto_category_id and auto_merchant_name
        for txn in transactions:
            if txn.id in suggestion_map:
                suggestion = suggestion_map[txn.id]
                txn.auto_category_id = suggestion.category_id
                txn.auto_merchant_name = suggestion.merchant_name
                if txn.auto_category_id is not None:
                    logger.debug(
                        f"Transaction {txn.id[:8]}... auto-categorized as {txn.auto_category_id}"
                    )
                if txn.auto_merchant_name is not None:
                    logger.debug(
                        f"Transaction {txn.id[:8]}... merchant detected as '{txn.auto_merchant_name}'"
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


def auto_categorize_for_import_batch(
    db_manager,
    config: Optional[Config],
    data_import_id: int,
    batch_size: int,
) -> ImportBatchLoad:
    """Load and auto-categorize the next unreviewed batch for a data import.

    Fetches up to ``batch_size`` unreviewed transactions for the import. For
    rows that don't yet have an LLM suggestion (auto_category_id IS NULL), and
    only when the LLM is enabled, runs auto-categorization using historical
    examples from the same account, then persists the new auto_category_id /
    auto_merchant_name values.

    Re-running this for the same batch (e.g. on a page refresh) is a no-op for
    the LLM: once auto suggestions are persisted the rows are no longer
    "missing", so the provider is not called again.

    Args:
        db_manager: Database manager instance.
        config: Application configuration (None or llm_enabled=False skips LLM).
        data_import_id: The data import being reviewed.
        batch_size: Maximum number of transactions in the batch.

    Returns:
        ImportBatchLoad with the (re-fetched) batch and an llm_failed flag.
    """
    # Imported here to avoid a circular import at module load time.
    from repositories.categories import CategoryRepository
    from repositories.transactions import TransactionRepository

    transactions_repo = TransactionRepository(db_manager)
    batch = transactions_repo.find_next_unreviewed_batch(data_import_id, batch_size)
    if not batch:
        return ImportBatchLoad(transactions=[], llm_failed=False)

    missing = [t for t in batch if t.auto_category_id is None]
    llm_failed = False

    if missing and config is not None and getattr(config, "llm_enabled", False):
        # Establish a usable provider first so we can distinguish a real failure
        # (e.g. bad API key) from the LLM simply being disabled.
        provider = None
        try:
            provider = get_llm_provider(config)
        except Exception as e:
            logger.error(f"LLM provider unavailable for import batch: {e}")
            llm_failed = True

        if provider is not None:
            account_id = batch[0].account_id
            historical = transactions_repo.find_historical_for_categorization(
                account_id, limit=200
            )
            categories = CategoryRepository(db_manager).find_all()
            categorized = auto_categorize(missing, categories, historical, config)
            to_update = [
                t
                for t in categorized
                if t.auto_category_id is not None or t.auto_merchant_name is not None
            ]
            if to_update:
                transactions_repo.batch_update(
                    to_update, ["auto_category_id", "auto_merchant_name"]
                )

    # Re-fetch so the returned batch reflects what's persisted on disk.
    refreshed = transactions_repo.find_next_unreviewed_batch(data_import_id, batch_size)
    return ImportBatchLoad(transactions=refreshed, llm_failed=llm_failed)
