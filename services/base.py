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
        from services.accounts import AccountService
        from services.transactions import TransactionService
        from services.data_imports import DataImportService
        from services.categories import CategoryService

        self.accounts = AccountService(self.db_manager)
        self.transactions = TransactionService(self.db_manager)
        self.data_imports = DataImportService(self.db_manager)
        self.categories = CategoryService(self.db_manager)
