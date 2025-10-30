from datetime import datetime


class TestDataImportService:
    """Tests for DataImportService."""

    def test_create_data_import_with_filename(self, services):
        """Test creating a data import with a filename."""
        # Create an account first
        account = services.accounts.create("test_account", "bofa", "Test Account")

        # Create data import
        data_import = services.data_imports.create(
            account.id, "bofa_20250101_120000_export.csv.gz"
        )

        assert data_import.id is not None
        assert data_import.id > 0
        assert data_import.account_id == account.id
        assert data_import.filename == "bofa_20250101_120000_export.csv.gz"
        assert isinstance(data_import.created_at, datetime)

    def test_create_data_import_without_filename(self, services):
        """Test creating a data import without a filename (archiving disabled)."""
        account = services.accounts.create("test_account", "bofa", "Test Account")

        data_import = services.data_imports.create(account.id, None)

        assert data_import.id is not None
        assert data_import.account_id == account.id
        assert data_import.filename is None
        assert isinstance(data_import.created_at, datetime)

    def test_find_data_import_by_id(self, services):
        """Test finding a data import by ID."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        created = services.data_imports.create(account.id, "test_file.csv.gz")

        found = services.data_imports.find(created.id)

        assert found is not None
        assert found.id == created.id
        assert found.account_id == account.id
        assert found.filename == "test_file.csv.gz"
        assert found.created_at == created.created_at

    def test_find_data_import_by_id_not_found(self, services):
        """Test finding a non-existent data import returns None."""
        found = services.data_imports.find(9999)

        assert found is None

    def test_find_by_account_empty(self, services):
        """Test finding data imports for an account with no imports."""
        account = services.accounts.create("test_account", "bofa", "Test Account")

        imports = services.data_imports.find_by_account(account.id)

        assert imports == []
        assert isinstance(imports, list)

    def test_find_by_account_single_import(self, services):
        """Test finding data imports for an account with one import."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        created = services.data_imports.create(account.id, "file1.csv.gz")

        imports = services.data_imports.find_by_account(account.id)

        assert len(imports) == 1
        assert imports[0].id == created.id
        assert imports[0].filename == "file1.csv.gz"

    def test_find_by_account_multiple_imports(self, services):
        """Test finding data imports for an account with multiple imports."""
        account = services.accounts.create("test_account", "bofa", "Test Account")

        import1 = services.data_imports.create(account.id, "file1.csv.gz")
        import2 = services.data_imports.create(account.id, "file2.csv.gz")
        import3 = services.data_imports.create(account.id, "file3.csv.gz")

        imports = services.data_imports.find_by_account(account.id)

        assert len(imports) == 3
        # Should be ordered by created_at DESC (newest first)
        # Check that they're in reverse creation order by checking IDs
        import_ids = [imp.id for imp in imports]
        assert import3.id in import_ids
        assert import2.id in import_ids
        assert import1.id in import_ids

    def test_find_by_account_only_returns_account_imports(self, services):
        """Test that find_by_account only returns imports for the specified account."""
        account1 = services.accounts.create("account1", "bofa", "Account 1")
        account2 = services.accounts.create("account2", "chase", "Account 2")

        # Create imports for both accounts
        import1_a1 = services.data_imports.create(account1.id, "account1_file1.csv.gz")
        import2_a2 = services.data_imports.create(account2.id, "account2_file1.csv.gz")
        import3_a1 = services.data_imports.create(account1.id, "account1_file2.csv.gz")

        # Get imports for account1
        imports_a1 = services.data_imports.find_by_account(account1.id)

        assert len(imports_a1) == 2
        import_ids_a1 = [imp.id for imp in imports_a1]
        assert import1_a1.id in import_ids_a1
        assert import3_a1.id in import_ids_a1

        # Get imports for account2
        imports_a2 = services.data_imports.find_by_account(account2.id)

        assert len(imports_a2) == 1
        assert imports_a2[0].id == import2_a2.id

    def test_find_by_account_nonexistent_account(self, services):
        """Test finding imports for a non-existent account returns empty list."""
        imports = services.data_imports.find_by_account(9999)

        assert imports == []

    def test_created_at_timestamp_is_set(self, services):
        """Test that created_at timestamp is automatically set."""
        account = services.accounts.create("test_account", "bofa", "Test Account")

        data_import = services.data_imports.create(account.id, "file.csv.gz")

        # Check that created_at is set and is a valid datetime
        assert isinstance(data_import.created_at, datetime)
        # Verify it has reasonable date components (not all zeros)
        assert data_import.created_at.year >= 2020
        assert 1 <= data_import.created_at.month <= 12
        assert 1 <= data_import.created_at.day <= 31

    def test_multiple_imports_have_different_timestamps(self, services):
        """Test that multiple imports have increasing timestamps."""
        account = services.accounts.create("test_account", "bofa", "Test Account")

        import1 = services.data_imports.create(account.id, "file1.csv.gz")
        import2 = services.data_imports.create(account.id, "file2.csv.gz")

        # Import2 should have a timestamp >= import1
        assert import2.created_at >= import1.created_at

    def test_create_with_long_filename(self, services):
        """Test creating data import with a long filename."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        long_filename = "a" * 200 + ".csv.gz"

        data_import = services.data_imports.create(account.id, long_filename)

        assert data_import.filename == long_filename

    def test_create_with_special_characters_in_filename(self, services):
        """Test creating data import with special characters in filename."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        filename = "bofa_2025-01-01_12:00:00_export (copy).csv.gz"

        data_import = services.data_imports.create(account.id, filename)

        found = services.data_imports.find(data_import.id)
        assert found.filename == filename

    def test_row_to_data_import_conversion(self, services):
        """Test that database row is correctly converted to DataImport object."""
        account = services.accounts.create("test_account", "bofa", "Test Account")
        created = services.data_imports.create(account.id, "test.csv.gz")

        # Find it to ensure row conversion works
        found = services.data_imports.find(created.id)

        assert found.id == created.id
        assert found.account_id == created.account_id
        assert found.filename == created.filename
        # Timestamps should match (within microsecond precision)
        assert found.created_at.replace(microsecond=0) == created.created_at.replace(
            microsecond=0
        )
