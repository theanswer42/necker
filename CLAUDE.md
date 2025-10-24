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

### Running the Application
```bash
python main.py
# or
uv run python main.py
```

### Development Tools
```bash
# Code formatting and linting
ruff check
ruff format

# Install development dependencies
uv sync --group dev
```

## Project Structure

- `main.py` - Entry point with basic "Hello from necker!" output
- `samples/` - Contains sample CSV files from different banks (scan only when specifically needed for tasks):
  - `amex.csv` - American Express transaction format
  - `bofa.csv` - Bank of America transaction format  
  - `chase.csv` - Chase transaction format
- `pyproject.toml` - Project configuration and dependencies
- `uv.lock` - Dependency lock file

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