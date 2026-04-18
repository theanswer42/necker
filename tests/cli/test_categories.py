"""Tests for CLI category commands."""

import pytest
from argparse import Namespace
from unittest.mock import patch

from cli.categories import cmd_delete, cmd_seed


class TestCmdDelete:
    """Tests for cmd_delete."""

    def test_unknown_category_exits(self, services, output):
        args = Namespace(category_id=9999)
        with pytest.raises(SystemExit) as exc:
            cmd_delete(args, services.db_manager, services.config, output)
        assert exc.value.code == 1

    def test_cancel_deletion_does_not_delete(self, services, output):
        category = services.categories.create("Food", "Food expenses")
        args = Namespace(category_id=category.id)
        with patch("builtins.input", return_value="no"):
            cmd_delete(args, services.db_manager, services.config, output)
        assert services.categories.find(category.id) is not None

    def test_confirm_deletion_deletes_category(self, services, output):
        category = services.categories.create("Food", "Food expenses")
        args = Namespace(category_id=category.id)
        with patch("builtins.input", return_value="yes"):
            cmd_delete(args, services.db_manager, services.config, output)
        assert services.categories.find(category.id) is None


class TestCmdSeed:
    """Tests for cmd_seed."""

    def test_seed_creates_categories(self, services, output):
        args = Namespace()
        cmd_seed(args, services.db_manager, services.config, output)
        categories = services.categories.find_all()
        assert len(categories) > 0

    def test_seed_creates_parent_and_child_categories(self, services, output):
        args = Namespace()
        cmd_seed(args, services.db_manager, services.config, output)
        categories = services.categories.find_all()
        names = {c.name for c in categories}
        # housing is a known parent in the seed file
        assert "housing" in names
        # housing/rent is a known child
        assert "housing/rent" in names

    def test_seed_is_idempotent(self, services, output):
        args = Namespace()
        cmd_seed(args, services.db_manager, services.config, output)
        count_after_first = len(services.categories.find_all())

        cmd_seed(args, services.db_manager, services.config, output)
        count_after_second = len(services.categories.find_all())

        assert count_after_first == count_after_second

    def test_seed_file_not_found_exits(self, services, output):
        args = Namespace()
        with patch("cli.categories.Path.exists", return_value=False):
            with pytest.raises(SystemExit) as exc:
                cmd_seed(args, services.db_manager, services.config, output)
        assert exc.value.code == 1
