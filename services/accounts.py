"""Account service — business logic for account creation."""

import re

from ingestion import get_available_modules


def create_account(services, name: str, account_type: str, description: str):
    """Create a new account with validation.

    Args:
        services: Services DI container.
        name: Account name (must match ^[a-z_]+$).
        account_type: Ingestion module name (must be in get_available_modules()).
        description: Human-readable description (must be non-empty after strip).

    Returns:
        Account: The newly created account.

    Raises:
        ValueError: If any validation fails or name already exists.
    """
    if not re.fullmatch(r"[a-z_]+", name):
        raise ValueError(
            f"Account name '{name}' is invalid. "
            "Only lowercase letters and underscores are allowed."
        )

    available = get_available_modules()
    if account_type not in available:
        raise ValueError(
            f"Invalid account type '{account_type}'. "
            f"Must be one of: {', '.join(available)}"
        )

    if not description.strip():
        raise ValueError("Description cannot be empty.")

    if services.accounts.find_by_name(name) is not None:
        raise ValueError(f"Account name '{name}' already exists.")

    return services.accounts.create(name, account_type, description)
