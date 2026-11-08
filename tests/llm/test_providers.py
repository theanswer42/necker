"""Tests for LLM provider implementations.

The SDK call is replaced with an autospec'd mock built from the real SDK
method, so any kwarg the installed SDK no longer accepts raises TypeError
here instead of at runtime against the live API.
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import create_autospec

from llm.providers.anthropic import AnthropicProvider
from llm.providers.anthropic import (
    CategorizationResponse as AnthropicCategorizationResponse,
)
from llm.providers.anthropic import (
    TransactionCategorization as AnthropicTransactionCategorization,
)
from llm.providers.openai import CategorizationResponse as OpenAICategorizationResponse
from llm.providers.openai import OpenAIProvider
from llm.providers.openai import (
    TransactionCategorization as OpenAITransactionCategorization,
)
from models.category import Category
from models.transaction import Transaction


def _transaction() -> Transaction:
    return Transaction(
        id="txn-1",
        account_id=1,
        transaction_date=date(2026, 1, 15),
        post_date=None,
        description="STARBUCKS #123",
        bank_category=None,
        amount=550,
        transaction_type="expense",
    )


def _categories() -> list[Category]:
    return [Category(id=7, name="Coffee", description=None)]


class TestAnthropicProvider:
    def test_parse_call_matches_sdk_signature(self):
        provider = AnthropicProvider(api_key="test-key")
        parsed = AnthropicCategorizationResponse(
            categorizations=[
                AnthropicTransactionCategorization(
                    transaction_id="txn-1", category_id=7, merchant_name="Starbucks"
                )
            ]
        )
        mock_parse = create_autospec(
            provider.client.messages.parse,
            return_value=SimpleNamespace(parsed_output=parsed),
        )
        provider.client.messages.parse = mock_parse

        suggestions = provider.categorize_transactions(
            [_transaction()], _categories(), []
        )

        mock_parse.assert_called_once()
        kwargs = mock_parse.call_args.kwargs
        assert "temperature" not in kwargs
        assert kwargs["output_format"] is AnthropicCategorizationResponse
        assert len(suggestions) == 1
        assert suggestions[0].transaction_id == "txn-1"
        assert suggestions[0].category_id == 7
        assert suggestions[0].merchant_name == "Starbucks"

    def test_null_parsed_output_returns_empty(self):
        provider = AnthropicProvider(api_key="test-key")
        provider.client.messages.parse = create_autospec(
            provider.client.messages.parse,
            return_value=SimpleNamespace(parsed_output=None),
        )

        assert provider.categorize_transactions([_transaction()], [], []) == []


class TestOpenAIProvider:
    def test_parse_call_matches_sdk_signature(self):
        provider = OpenAIProvider(api_key="test-key")
        parsed = OpenAICategorizationResponse(
            categorizations=[
                OpenAITransactionCategorization(
                    transaction_id="txn-1", category_id=7, merchant_name="Starbucks"
                )
            ]
        )
        completions = provider.client.beta.chat.completions
        mock_parse = create_autospec(
            completions.parse,
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))]
            ),
        )
        completions.parse = mock_parse

        suggestions = provider.categorize_transactions(
            [_transaction()], _categories(), []
        )

        mock_parse.assert_called_once()
        assert (
            mock_parse.call_args.kwargs["response_format"]
            is OpenAICategorizationResponse
        )
        assert len(suggestions) == 1
        assert suggestions[0].category_id == 7
        assert suggestions[0].merchant_name == "Starbucks"
