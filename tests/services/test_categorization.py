"""Tests for auto_categorize service function."""

from datetime import date
from unittest.mock import MagicMock, patch


from models.category import Category
from models.transaction import Transaction
from llm.providers.base import CategorySuggestion
from services.categorization import auto_categorize


def _make_transaction(description="Coffee", amount=500, account_id=1):
    return Transaction.create_with_checksum(
        raw_data=f"01/15/2024,{description},-5.00,995.00",
        account_id=account_id,
        transaction_date=date(2024, 1, 15),
        post_date=None,
        description=description,
        bank_category=None,
        amount=amount,
        transaction_type="expense",
    )


def _make_category(id=1, name="Food"):
    return Category(id=id, name=name, description="Food expenses", parent_id=None)


def _make_config(llm_enabled=True):
    config = MagicMock()
    config.llm_enabled = llm_enabled
    return config


class TestAutoCategorizeSkipPaths:
    """Tests for early-return branches that skip LLM categorization."""

    def test_no_config_returns_transactions_unchanged(self):
        transactions = [_make_transaction()]
        categories = [_make_category()]
        result = auto_categorize(transactions, categories, [], config=None)
        assert result is transactions
        assert result[0].auto_category_id is None

    def test_llm_disabled_returns_transactions_unchanged(self):
        config = _make_config(llm_enabled=False)
        transactions = [_make_transaction()]
        categories = [_make_category()]
        with patch("services.categorization.get_llm_provider", return_value=None):
            result = auto_categorize(transactions, categories, [], config=config)
        assert result is transactions
        assert result[0].auto_category_id is None

    def test_provider_none_returns_transactions_unchanged(self):
        config = _make_config()
        transactions = [_make_transaction()]
        categories = [_make_category()]
        with patch("services.categorization.get_llm_provider", return_value=None):
            result = auto_categorize(transactions, categories, [], config=config)
        assert result is transactions
        assert result[0].auto_category_id is None

    def test_no_categories_returns_transactions_unchanged(self):
        config = _make_config()
        mock_provider = MagicMock()
        transactions = [_make_transaction()]
        with patch(
            "services.categorization.get_llm_provider", return_value=mock_provider
        ):
            result = auto_categorize(transactions, [], [], config=config)
        assert result is transactions
        mock_provider.categorize_transactions.assert_not_called()

    def test_provider_init_error_returns_transactions_unchanged(self):
        config = _make_config()
        transactions = [_make_transaction()]
        categories = [_make_category()]
        with patch(
            "services.categorization.get_llm_provider",
            side_effect=Exception("API key invalid"),
        ):
            result = auto_categorize(transactions, categories, [], config=config)
        assert result is transactions
        assert result[0].auto_category_id is None

    def test_llm_call_error_returns_transactions_unchanged(self):
        config = _make_config()
        mock_provider = MagicMock()
        mock_provider.categorize_transactions.side_effect = Exception("LLM timeout")
        transactions = [_make_transaction()]
        categories = [_make_category()]
        with patch(
            "services.categorization.get_llm_provider", return_value=mock_provider
        ):
            result = auto_categorize(transactions, categories, [], config=config)
        assert result is transactions
        assert result[0].auto_category_id is None


class TestAutoCategorizeSuccess:
    """Tests for successful LLM categorization paths."""

    def test_sets_auto_category_id_from_suggestion(self):
        config = _make_config()
        txn = _make_transaction()
        category = _make_category(id=7)
        suggestion = CategorySuggestion(
            transaction_id=txn.id, category_id=7, merchant_name=None
        )
        mock_provider = MagicMock()
        mock_provider.categorize_transactions.return_value = [suggestion]

        with patch(
            "services.categorization.get_llm_provider", return_value=mock_provider
        ):
            result = auto_categorize([txn], [category], [], config=config)

        assert result[0].auto_category_id == 7

    def test_sets_auto_merchant_name_from_suggestion(self):
        config = _make_config()
        txn = _make_transaction("SBUX #1234")
        category = _make_category()
        suggestion = CategorySuggestion(
            transaction_id=txn.id, category_id=1, merchant_name="Starbucks"
        )
        mock_provider = MagicMock()
        mock_provider.categorize_transactions.return_value = [suggestion]

        with patch(
            "services.categorization.get_llm_provider", return_value=mock_provider
        ):
            result = auto_categorize([txn], [category], [], config=config)

        assert result[0].auto_merchant_name == "Starbucks"

    def test_unrecognized_transaction_id_leaves_fields_none(self):
        config = _make_config()
        txn = _make_transaction()
        category = _make_category()
        # Suggestion references a different transaction ID
        suggestion = CategorySuggestion(
            transaction_id="unknown_id", category_id=1, merchant_name="Store"
        )
        mock_provider = MagicMock()
        mock_provider.categorize_transactions.return_value = [suggestion]

        with patch(
            "services.categorization.get_llm_provider", return_value=mock_provider
        ):
            result = auto_categorize([txn], [category], [], config=config)

        assert result[0].auto_category_id is None
        assert result[0].auto_merchant_name is None

    def test_partial_suggestions_applied_correctly(self):
        config = _make_config()
        txn1 = _make_transaction("Coffee")
        txn2 = _make_transaction("Bus")
        category = _make_category()
        # Only txn1 gets a suggestion
        suggestion = CategorySuggestion(
            transaction_id=txn1.id, category_id=1, merchant_name=None
        )
        mock_provider = MagicMock()
        mock_provider.categorize_transactions.return_value = [suggestion]

        with patch(
            "services.categorization.get_llm_provider", return_value=mock_provider
        ):
            result = auto_categorize([txn1, txn2], [category], [], config=config)

        assert result[0].auto_category_id == 1
        assert result[1].auto_category_id is None

    def test_passes_historical_transactions_to_provider(self):
        config = _make_config()
        txn = _make_transaction()
        historical = [_make_transaction("Old Coffee")]
        category = _make_category()
        mock_provider = MagicMock()
        mock_provider.categorize_transactions.return_value = []

        with patch(
            "services.categorization.get_llm_provider", return_value=mock_provider
        ):
            auto_categorize([txn], [category], historical, config=config)

        call_args = mock_provider.categorize_transactions.call_args
        assert call_args[0][2] is historical

    def test_suggestion_with_none_category_id_leaves_auto_category_none(self):
        config = _make_config()
        txn = _make_transaction()
        category = _make_category()
        suggestion = CategorySuggestion(
            transaction_id=txn.id, category_id=None, merchant_name="Starbucks"
        )
        mock_provider = MagicMock()
        mock_provider.categorize_transactions.return_value = [suggestion]

        with patch(
            "services.categorization.get_llm_provider", return_value=mock_provider
        ):
            result = auto_categorize([txn], [category], [], config=config)

        assert result[0].auto_category_id is None
        assert result[0].auto_merchant_name == "Starbucks"

    def test_returns_same_list_object(self):
        config = _make_config()
        transactions = [_make_transaction()]
        category = _make_category()
        mock_provider = MagicMock()
        mock_provider.categorize_transactions.return_value = []

        with patch(
            "services.categorization.get_llm_provider", return_value=mock_provider
        ):
            result = auto_categorize(transactions, [category], [], config=config)

        assert result is transactions
