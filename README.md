# Necker

[![Tests](https://github.com/theanswer42/necker/actions/workflows/test.yml/badge.svg)](https://github.com/theanswer42/necker/actions)

A Python-based personal finance tool for ingesting and managing
transactions from multiple financial institutions. Named after Jacques
Necker, the economist put in charge of fixing the French economy
before the french revolution. (Let's ignore the fact that he could not
fix it and the revolution happened anyway).

Most of this project was built with Claude.

## Features

- **Multi-bank support**: Import transactions from Bank of America, Chase, American Express, and Discover
- **Transaction classification**: Automatically categorizes transactions as income, expense, or transfer
- **Deduplication**: SHA256 checksum-based transaction IDs prevent duplicate imports
- **Transfer tracking**: Identifies transfers between accounts (credit card payments, etc.)
- **Rich metadata**: Stores additional transaction details like running balances, addresses, and memo fields
- **Database migrations**: Schema versioning with migration support

## Installation

This project uses [uv](https://github.com/astral-sh/uv) as the Python package manager. Requires Python 3.13+.

```bash
# Install dependencies
uv sync

# Install development dependencies
uv sync --group dev
```

## Quick Start

### 1. Initialize the Database

Run migrations to create the database schema:

```bash
uv run python -m cli migrate apply
```

Check migration status:

```bash
uv run python -m cli migrate status
```

### 2. Create Accounts

Create an account for each financial institution:

```bash
uv run python -m cli accounts create
```

You'll be prompted for:
- **Account name**: Identifier (e.g., `bofa_checking`, `chase_sapphire`)
- **Account type**: Must match an ingestion module (`bofa`, `chase`, `amex`, `discover`)
- **Description**: Human-readable description

List existing accounts:

```bash
uv run python -m cli accounts list
```

### 3. Import Transactions

Import transactions from a CSV file:

```bash
uv run python -m cli transactions ingest <csv_file> --account-name <account_name>
```

Examples:

```bash
# Import Bank of America transactions
uv run python -m cli transactions ingest samples/bofa.csv --account-name bofa_checking

# Import Chase credit card transactions
uv run python -m cli transactions ingest samples/chase.csv --account-name chase_card

# Import American Express transactions
uv run python -m cli transactions ingest samples/amex.csv --account-name amex_card

# Import Discover transactions
uv run python -m cli transactions ingest samples/discover.csv --account-name discover_card
```

**Note**: Duplicate transactions (identified by checksum) are automatically skipped.

## Supported Institutions

### Bank of America (`bofa`)

**CSV Format**: Includes summary section followed by transaction data

**Expected Headers**: `Date`, `Description`, `Amount`, `Running Bal.`

**Features**:
- Captures running balance in metadata
- Automatically detects credit card payments as transfers

**Transfer Detection**:
- Discover payments: `DISCOVER DES:E-PAYMENT`
- Chase payments: `CHASE CREDIT CRD DES:AUTOPAY`
- Amex payments: `AMERICAN EXPRESS DES:ACH PMT`

### Chase (`chase`)

**Expected Headers**: `Transaction Date`, `Post Date`, `Description`, `Category`, `Type`, `Amount`, `Memo`

**Features**:
- Captures both transaction and post dates
- Stores memo field in metadata
- Includes transaction categories

**Transfer Detection**:
- Type field = `Payment`
- Description contains `AUTOMATIC PAYMENT`

### American Express (`amex`)

**Expected Headers**: `Date`, `Description`, `Amount`, `Extended Details`, `Appears On Your Statement As`, `Address`, `City/State`, `Zip Code`, `Country`, `Reference`, `Category`

**Features**:
- Rich metadata: extended details, merchant address, reference numbers
- Handles multi-line CSV fields
- Detailed transaction categories

**Transfer Detection**:
- Description contains `AUTOPAY PAYMENT`

### Discover (`discover`)

**Expected Headers**: `Trans. Date`, `Post Date`, `Description`, `Amount`, `Category`

**Features**:
- Captures both transaction and post dates
- Includes transaction categories

**Transfer Detection**:
- Category = `Payments and Credits`
- Description starts with `DIRECTPAY FULL BALANCE`

## Transaction Types

Necker classifies all transactions into three types:

- **`income`**: Money received (deposits, refunds, credit card payments)
- **`expense`**: Money spent (purchases, bills, withdrawals)
- **`transfer`**: Money moved between your accounts (credit card payments that appear in both bank and credit card statements)

## CLI Reference

### Main CLI

```bash
# Show all available commands
uv run python -m cli --help

# Show help for a specific command
uv run python -m cli accounts --help
uv run python -m cli transactions --help
uv run python -m cli migrate --help
```

### Account Management

```bash
# Create a new account interactively
uv run python -m cli accounts create

# List all accounts
uv run python -m cli accounts list
```

### Transaction Import

```bash
# Import transactions from CSV
uv run python -m cli transactions ingest <csv_file> --account-name <account_name>

# Examples
uv run python -m cli transactions ingest transactions.csv --account-name bofa_checking
uv run python -m cli transactions ingest ~/Downloads/chase_2024.csv --account-name chase_card
```

### Database Migrations

```bash
# Apply all pending migrations
uv run python -m cli migrate apply

# Check migration status
uv run python -m cli migrate status
```

## Development

### Code Formatting

```bash
# Format code
uv run ruff format

# Check code
uv run ruff check
```

### Adding a New Institution

1. Create a new ingestion module in `ingestion/<institution>.py`
2. Define `_CSV_HEADERS` constant matching the CSV format
3. Implement `row_to_transaction(row: List[str], account_id: int) -> Transaction`
4. Implement `ingest(source: TextIO, account_id: int) -> List[Transaction]`
5. Register the module in `ingestion/__init__.py`

Example:

```python
# ingestion/mybank.py
import csv
from typing import List, TextIO
from models.transaction import Transaction

_CSV_HEADERS = ["Date", "Description", "Amount"]

def row_to_transaction(row: List[str], account_id: int) -> Transaction:
    # Parse row and return Transaction
    ...

def ingest(source: TextIO, account_id: int) -> List[Transaction]:
    # Validate headers and process CSV
    ...
```

Then register in `ingestion/__init__.py`:

```python
import ingestion.mybank as mybank

_INGESTION_MODULES = {
    # ...
    "mybank": mybank,
}
```

## Testing

This project includes comprehensive unit tests with 100% coverage of ingestion modules.

```bash
# Run all tests
uv run pytest

# Run tests with coverage report
uv run pytest --cov=ingestion --cov=services --cov=models --cov-report=term-missing

# Run tests in watch mode (requires pytest-watch)
uv run ptw
```

## TODO
- start building the tools layer
  - monthly summary
  - yearly summary
  - trends by category
- Budgets
- The first time we encounter an import with the header check failing,
  we should refactor to make that more robust

