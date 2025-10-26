"""Factory for creating LLM provider instances."""

from typing import Optional
from config import Config
from llm.providers.base import LLMProvider
from llm.providers.openai import OpenAIProvider
from logger import get_logger

logger = get_logger()


def get_llm_provider(config: Config) -> Optional[LLMProvider]:
    """Create an LLM provider instance based on configuration.

    Args:
        config: Application configuration.

    Returns:
        LLMProvider instance, or None if LLM is disabled.

    Raises:
        ValueError: If provider is configured but settings are invalid.
    """
    # Check if LLM is enabled
    if not hasattr(config, "llm_enabled") or not config.llm_enabled:
        logger.info("LLM categorization is disabled")
        return None

    provider_name = getattr(config, "llm_provider", None)

    if provider_name == "openai":
        api_key = getattr(config, "llm_openai_api_key", None)
        if not api_key:
            raise ValueError(
                "OpenAI provider selected but llm_openai_api_key not configured"
            )

        model = getattr(config, "llm_openai_model", None)
        logger.info(f"Initializing OpenAI provider (model: {model or 'default'})")

        return OpenAIProvider(api_key=api_key, model=model)

    elif provider_name is None:
        logger.info("No LLM provider configured")
        return None

    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
