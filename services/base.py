"""Base services container for dependency injection."""

from config import Config
from db.manager import DatabaseManager


class Services:
    """Container for all application services.

    This class provides a centralized way to access all services and makes
    it easy to inject mock services for testing.

    Args:
        config: Application configuration object.
        db_manager: Optional database manager for testing. If provided, config is ignored.
    """

    def __init__(self, config: Config, db_manager=None):
        """Initialize services with configuration.

        Args:
            config: Config object containing application configuration.
            db_manager: Optional database manager for dependency injection (testing).
                       If None, creates DatabaseManager from config.
        """
        self.config = config
        self.db_manager = db_manager or DatabaseManager(config)

        # Lazy import to avoid circular dependencies
        from repositories.accounts import AccountRepository
        from repositories.transactions import TransactionRepository
        from repositories.data_imports import DataImportRepository
        from repositories.categories import CategoryRepository
        from repositories.budgets import BudgetRepository

        self.accounts = AccountRepository(self.db_manager)
        self.transactions = TransactionRepository(self.db_manager)
        self.data_imports = DataImportRepository(self.db_manager)
        self.categories = CategoryRepository(self.db_manager)
        self.budgets = BudgetRepository(self.db_manager)
