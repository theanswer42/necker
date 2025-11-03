"""OpenAI provider implementation using structured outputs."""

from typing import List, Optional
from pydantic import BaseModel
from openai import OpenAI
from llm.providers.base import LLMProvider, CategorySuggestion
from llm.prompts.loader import PromptManager
from models.transaction import Transaction
from models.category import Category
from logger import get_logger

logger = get_logger()


# Pydantic models for structured output
class TransactionCategorization(BaseModel):
    """Single transaction categorization result."""

    transaction_id: str
    category_id: Optional[int] = None
    merchant_name: Optional[str] = None
    reasoning: Optional[str] = None


class CategorizationResponse(BaseModel):
    """Full categorization response with all transactions."""

    categorizations: List[TransactionCategorization]


class OpenAIProvider(LLMProvider):
    """OpenAI implementation using structured outputs for reliable JSON parsing."""

    def __init__(self, api_key: str, model: Optional[str] = None):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key.
            model: Model to use (e.g., "gpt-4o-mini"). If None, uses prompt default.
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.prompt_manager = PromptManager()

    def categorize_transactions(
        self,
        transactions: List[Transaction],
        categories: List[Category],
        historical_transactions: List[Transaction],
    ) -> List[CategorySuggestion]:
        """Categorize transactions using OpenAI with structured outputs.

        Args:
            transactions: List of transactions to categorize.
            categories: List of available categories.
            historical_transactions: Previously categorized transactions as examples.

        Returns:
            List of CategorySuggestion objects.

        Raises:
            Exception: If OpenAI API call fails.
        """
        if not transactions:
            return []

        logger.info(
            f"Calling OpenAI to categorize {len(transactions)} transaction(s) "
            f"with {len(historical_transactions)} historical examples"
        )

        # Format data for the prompt
        categories_text = self._format_categories(categories)
        examples_text = self._format_historical_transactions(
            historical_transactions, categories
        )
        transactions_text = self._format_transactions(transactions)

        # Load and render prompt
        rendered_prompt = self.prompt_manager.render_prompt(
            "categorization",
            {
                "categories": categories_text,
                "examples": examples_text,
                "transactions": transactions_text,
            },
        )

        # Determine model to use
        model = self.model or rendered_prompt["parameters"].get("model", "gpt-4o-mini")
        temperature = rendered_prompt["parameters"].get("temperature", 0.1)
        max_tokens = rendered_prompt["parameters"].get("max_tokens", 4000)

        logger.info(
            f"Using model: {model}, prompt version: {rendered_prompt['version']}"
        )

        # Call OpenAI with structured outputs
        try:
            response = self.client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": rendered_prompt["system_prompt"]},
                    {"role": "user", "content": rendered_prompt["user_prompt"]},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=CategorizationResponse,
            )

            # Parse structured response
            result = response.choices[0].message.parsed

            if result is None:
                logger.warning("OpenAI returned null parsed response")
                return []

            # Convert to CategorySuggestion objects
            suggestions = []
            for cat in result.categorizations:
                suggestions.append(
                    CategorySuggestion(
                        transaction_id=cat.transaction_id,
                        category_id=cat.category_id,
                        merchant_name=cat.merchant_name,
                        confidence=None,  # OpenAI doesn't provide confidence scores
                        reasoning=cat.reasoning,
                    )
                )

            logger.info(
                f"Successfully categorized {len([s for s in suggestions if s.category_id is not None])} "
                f"out of {len(transactions)} transactions"
            )

            return suggestions

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _format_categories(self, categories: List[Category]) -> str:
        """Format categories for the prompt."""
        if not categories:
            return "No categories available."

        lines = []
        for cat in categories:
            desc = f" - {cat.description}" if cat.description else ""
            lines.append(f"- ID {cat.id}: {cat.name}{desc}")

        return "\n".join(lines)

    def _format_historical_transactions(
        self, transactions: List[Transaction], categories: List[Category]
    ) -> str:
        """Format historical transactions with their categories."""
        if not transactions:
            return "No historical examples available."

        # Create category lookup
        cat_lookup = {cat.id: cat.name for cat in categories}

        lines = []
        for txn in transactions[:50]:  # Limit to 50 examples to avoid token limits
            category_name = cat_lookup.get(txn.category_id, "Unknown")
            merchant_part = (
                f", Merchant: '{txn.merchant_name}'" if txn.merchant_name else ""
            )
            lines.append(
                f"- Description: '{txn.description}', "
                f"Amount: ${txn.amount}, "
                f"Type: {txn.type}, "
                f"Category: {category_name} (ID {txn.category_id}){merchant_part}"
            )

        return "\n".join(lines)

    def _format_transactions(self, transactions: List[Transaction]) -> str:
        """Format transactions to categorize."""
        lines = []
        for txn in transactions:
            lines.append(
                f"- ID: {txn.id}, "
                f"Description: '{txn.description}', "
                f"Amount: ${txn.amount}, "
                f"Type: {txn.type}"
            )

        return "\n".join(lines)
