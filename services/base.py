"""Base services container for dependency injection."""

from db import manager as dbmgr


class Services:
    """Container for all application services.

    This class provides a centralized way to access all services and makes
    it easy to inject mock services for testing.

    Args:
        db_manager: Database manager instance. Defaults to the global dbmgr.
    """

    def __init__(self, db_manager=None):
        """Initialize services with optional database manager.

        Args:
            db_manager: Optional database manager for dependency injection.
                       If None, uses the default global dbmgr.
        """
        self.db_manager = db_manager or dbmgr

        # Lazy import to avoid circular dependencies
        from services.accounts import AccountService
        from services.transactions import TransactionService

        self.accounts = AccountService(self.db_manager)
        self.transactions = TransactionService(self.db_manager)
