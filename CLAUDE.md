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
- `services/` contains the `Services` dependency-injection container
  that exposes repositories, plus business logic modules (`analysis.py`,
  `categorization.py`, `ingestion.py`)

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
- **services layer** (`services/`): business logic — ingestion orchestration, analysis, auto-categorization; also hosts the `Services` DI container
- **interface layer** (`cli/`): input validation and output only — delegates all logic to services

The `Services` class in `services/base.py` is the central dependency-injection container. It wires together the database manager and all repositories, and is passed through to service functions and CLI commands.
