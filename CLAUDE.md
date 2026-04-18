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

If you modified any file in `app/templates/` or `app/static/src/input.css`, you must also rebuild the Tailwind CSS:
```bash
./scripts/build-css.sh
```
Commit the updated `app/static/dist/app.css` along with your template changes.

## Tailwind CSS

The web UI uses [Tailwind CSS v3.4.17](https://github.com/tailwindlabs/tailwindcss/releases/tag/v3.4.17) via the standalone CLI binary (no Node.js required). The binary is **not** checked into the repo.

**Setup (one-time)**:
1. Download the standalone binary for your platform from:
   `https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64`
   (replace `linux-x64` with your platform, e.g. `macos-arm64`)
2. Place it at `/usr/local/bin/tailwindcss` (or anywhere on PATH) and `chmod +x`.

**Rebuild CSS** (after template or `input.css` changes):
```bash
./scripts/build-css.sh          # one-shot, minified
./scripts/build-css.sh --watch  # watch mode for development
```

Key files:
- `app/static/src/input.css` — Tailwind directives + `@layer components` utility classes
- `tailwind.config.js` — content paths for JIT scanning
- `app/static/dist/app.css` — built output (committed to repo)

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

## CLI Output Conventions

Every `cmd_*` in `cli/` routes its emissions onto three distinct streams. When adding a new command or editing an existing one, classify each line before writing it:

- **log** → `logger.info/warning/error` (stderr). Progress, status, confirmations, error messages. Anything that narrates what the command is doing.
- **output** → `OutputWriter.record/collection/section` (stdout). The actual data the command produces: a created record, a list of rows, a report payload, a result summary. Always via a typed dataclass.
- **interaction** → direct `print`/`input` (stdout). Prompts in `create`/`delete` flows and confirmation questions.

The split exists so `python -m cli … | cat` yields only data on stdout, with logs on stderr. Don't cross the streams — e.g. don't `print` structured data, and don't `logger.info` a prompt.

Output dataclass rules:
- Existing model dataclasses (`Account`, `Category`, `Budget`, `Transaction`) go straight to the writer.
- Results that don't already have a typed shape (ingest result, migration status, backup result, etc.) get a dataclass in `cli/outputs.py`.
- Field-level rendering hints live on the dataclass as `field(metadata=...)`:
  - `cli_format: "cents_to_dollars"` for integer-cents amount fields
  - `cli_format: "iso_date"` for `date`/`datetime` fields
  - `cli_label: "..."` to override the displayed field name
- Metadata sits on the model dataclass (source of truth for the field's domain), not on a per-command display wrapper.

Every `cmd_*` takes `output: OutputWriter` as its last positional parameter. `cli/__main__.py` constructs the writer and dispatches. `cli/server.py` is the exception — it starts Flask and has no data output.

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
