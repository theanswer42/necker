# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Necker is a Python project that appears to be designed for processing financial data, specifically bank transaction CSV files. The project includes sample CSV files from major banks (American Express, Bank of America, Chase) with transaction data including dates, descriptions, amounts, and categorization.

## Development Setup

This project uses `uv` as the Python package manager. The project requires Python 3.13 or higher.

### Installation
```bash
uv sync
```

### Running Commands

**IMPORTANT**: ALL Python commands and tools must be run with `uv run` prefix. This includes:
- Python scripts: `uv run python script.py` (NOT `python script.py`)
- Python modules: `uv run python -m cli` (NOT `python -m cli`)
- Development tools: `uv run ruff check` (NOT `ruff check`)
- Any tool installed in the venv: `uv run <tool>` (NOT `<tool>`)

This ensures commands use the correct virtual environment managed by `uv`.

### Running the Application
```bash
uv run python -m cli
```

### Development Tools
```bash
# Code formatting and linting
uv run ruff check
uv run ruff format

# Install development dependencies
uv sync --group dev
```

## Project Structure
- `models/` contains our data models
- `cli/` contains the cli package. Modules in this package implement
  various subcommands needed.
- `ingestion/` contains ingestion modules - these convert CSVs from
  various financial institutions to Transaction objects
- `db/` contains code for database connection management, and
  migrations
- `llm/` contains code and prompts to communicate with LLMs
- `repositories/` contains repository classes — pure DB operations
  (SQL queries and row-to-object mapping) for each model
- `services/` contains business logic modules (e.g. `accounts.py`,
  `categorization.py`, `ingestion.py`)
- `reports/` contains typed analytical computations over raw data. Each
  report is a class with a `run()` method that accepts simple typed
  inputs and returns a typed dataclass defined in `models/reports.py`.

## Pre-commit Checks

**IMPORTANT**: Before creating ANY git commit, you MUST run the following and ensure they pass:
```bash
uv run ruff format .
uv run ruff check .
```
If `ruff check` reports errors, fix them before committing. Do not skip this step.

## Important Notes

- The `samples/` directory contains sample data files that should only be examined when specifically needed for development tasks
- When working on the codebase, focus on the main application files and avoid scanning sample data unless explicitly required

## Architecture Notes

The project follows a layered architecture:

- **repositories layer** (`repositories/`): pure DB operations — SQL queries and row-to-object mapping, no business logic
- **services layer** (`services/`): business logic — ingestion orchestration, auto-categorization, account management
- **reports layer** (`reports/`): typed analytical computations over raw data. Each report is a class with a `run()` method that accepts simple typed inputs and returns a typed dataclass (defined in `models/reports.py`). Reports may compose by calling other reports. Reports are consumed by the CLI, web UI, and API layers — they should not contain presentation logic.
- **interface layer** (`cli/`, `app/`): input validation and output only — delegates all logic to services and reports

Services and reports are instantiated with a `db_manager` directly; there is no central DI container.

## Database & Foreign Key Conventions

`PRAGMA foreign_keys = ON` is set on every connection (`db/manager.py`) and in the test fixture (`tests/conftest.py`). Foreign keys are enforced at runtime — declarations in migrations are not just documentation.

### ON DELETE policy

Every `*_id` column that references another table must have an explicit, intentional `ON DELETE` behavior. Use this decision framework:

- **`NO ACTION`** (the default — omit the `ON DELETE` clause) for **structural/ownership references** where the parent should not be deletable while children exist. This is the safe default. Examples: `transactions.account_id`, `transactions.data_import_id`, `categories.parent_id`.
- **`SET NULL`** for **loose tag/classification references** where the parent is metadata that can be removed without destroying the referencing row. The column must be nullable. Examples: `transactions.category_id`, `transactions.auto_category_id`.
- **`CASCADE`** should be used sparingly and only when deleting the parent truly means "delete everything underneath it." Before using CASCADE, verify the full cascade chain — in SQLite, cascades can chain through multiple tables, and a `NO ACTION` FK further down the chain may be bypassed if an intermediate cascade deletes the rows first (SQLite checks `NO ACTION` at end-of-statement, after cascades have propagated). If in doubt, use `NO ACTION` and let application code handle the teardown explicitly.

### When adding a new table or FK column

1. Always declare the `FOREIGN KEY` constraint in the `CREATE TABLE` statement (or inline on the column for self-referential FKs like `parent_id`).
2. Choose an `ON DELETE` action using the policy above. Do not rely on the default accidentally — make it a conscious choice.
3. Add an index on the FK column (SQLite does not auto-index foreign keys).
4. Write a test that verifies the FK is enforced (insert with a bogus ID → `IntegrityError`) and that the `ON DELETE` behavior is correct.
