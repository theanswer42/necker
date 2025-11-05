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
- `services/` contains code for relatively simple queries on the
  database
- `tools/` contains higher level tools that make use of the services

## Important Notes

- The `samples/` directory contains sample data files that should only be examined when specifically needed for development tasks
- When working on the codebase, focus on the main application files and avoid scanning sample data unless explicitly required

## Architecture Notes

The project is currently in early stages with a minimal main.py file. The presence of sample bank CSV files suggests this will be a financial data processing tool, likely for:
- Parsing different bank transaction formats
- Standardizing transaction data
- Categorizing transactions
- Financial analysis or reporting

The CSV samples show different bank formats with common fields like Date, Description, Amount, and Category, indicating the tool will need to handle format variations across different financial institutions.
