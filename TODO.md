# TODO — Architecture v2 Refactor

## Naming conventions for this refactor

- **repositories layer**: pure DB operations (current `services/*.py` classes) → moves to `repositories/` package
- **services layer**: business logic (current `tools/` + `categorization.py` + ingest orchestration) → stays in `services/` package
- **interface layers**: CLI, API, web — input/output only, delegate to services

---

## Phase 1: Restructure existing code into repositories/services/cli layers

### 1. Create `repositories/` package from current DB-access classes ✅

Move the four DB-access classes from `services/` into a new `repositories/` package.
These classes contain only SQL queries and row-to-object mapping — no business logic.

Files to create:
- `repositories/__init__.py`
- `repositories/accounts.py` (from `services/accounts.py` — `AccountService` class, rename to `AccountRepository`)
- `repositories/transactions.py` (from `services/transactions.py` — `TransactionService` class, rename to `TransactionRepository`)
- `repositories/categories.py` (from `services/categories.py` — `CategoryService` class, rename to `CategoryRepository`)
- `repositories/data_imports.py` (from `services/data_imports.py` — `DataImportService` class, rename to `DataImportRepository`)

Files to delete:
- `services/accounts.py`
- `services/transactions.py`
- `services/categories.py`
- `services/data_imports.py`

Update `services/base.py` to import from `repositories/` instead of `services/`. Keep the
`Services` container's attribute names (`self.accounts`, `self.transactions`, etc.)
unchanged for now — downstream code still references them.

Update all test files that directly import these classes (check `tests/services/`).

Run `uv run ruff check .` and `uv run pytest` to verify nothing is broken.

### 2. Move business logic into `services/` package ✅

Now that the DB-access classes have moved out of `services/`, repurpose `services/`
as the business logic layer.

Files to create:
- `services/analysis.py` — move the two functions (`get_period_transactions`,
  `get_period_summary`) from `tools/transactions.py`
- `services/categorization.py` — move the `auto_categorize` function from
  `categorization.py` (top-level)

Files to delete:
- `tools/transactions.py`
- `tools/__init__.py`
- `categorization.py`

Update `services/base.py`: the Services container should expose both data-layer
objects and service-layer functions/modules as needed. The exact wiring is up to
the implementer — the key constraint is that CLI code can call business logic
through the container.

Update `cli/transactions.py` to import `auto_categorize` from
`services.categorization` instead of `categorization`.

Update `tests/tools/test_transactions.py` — move to `tests/services/test_analysis.py`
and fix imports.

Run `uv run ruff check .` and `uv run pytest` to verify.

### 3. Extract ingest orchestration from CLI into services layer ✅

`cli/transactions.py::cmd_ingest` currently contains significant business logic:
CSV parsing via ingestion module, archive file creation, DataImport record creation,
bulk transaction insert, and auto-categorization. This should be a service.

Create `services/ingestion.py` with a function (e.g., `ingest_csv`) that:
- Takes the CSV file path, account, and services container (or individual repositories/service deps)
- Handles: ingestion module lookup, CSV parsing, archiving, DataImport creation,
  bulk insert, auto-categorization
- Returns a result object or dict with counts (parsed, inserted, skipped, categorized)

Slim down `cli/transactions.py::cmd_ingest` to: validate args, call the service,
print results. All the `logger.info` output for user feedback stays in the CLI layer;
the service should not print anything.

Similarly review `cmd_update_from_csv` — it also has business logic that could move
to a service, but this is lower priority. If it's straightforward, extract it too.

Run `uv run ruff check .` and `uv run pytest` to verify.

### 4. Clean up and verify the restructure ✅

Final verification pass:
- Ensure no imports reference deleted modules (`tools.*`, top-level `categorization`)
- Ensure `uv run ruff check .` passes with no errors
- Ensure `uv run pytest` passes with all tests green
- Ensure `uv run python -m cli --help` works and all subcommands are accessible
- Remove any empty `__init__.py` files or packages left behind
- Update CLAUDE.md project structure section to reflect the new layout

## Phase 2: Add Flask web server

### 5. Add Flask app factory and dependencies ✅

Implementation plan:
- Add `flask` to `pyproject.toml` dependencies
- Create `app/` package with `create_app()` factory, registering empty API/UI blueprints and serving `base.html` at `/`
- Create `app/templates/base.html` with htmx CDN script tag, nav, and content block
- Create `app/static/` directory placeholder
- Add `cli/server.py` with `cmd_serve` and register `serve` subcommand in `cli/__main__.py`
- Tests: Flask test client for app factory and root route

Add Flask as a dependency in `pyproject.toml` and run `uv sync`.

Create `app/` package with:
- `app/__init__.py`
- `app/app.py` — Flask app factory (`create_app()`) that:
  - Creates the Flask app
  - Initializes config, DatabaseManager, and Services container
  - Registers API and UI blueprints (empty for now)
  - Stores services on `app` (e.g., `app.services`) for access in routes
  - Serves `base.html` at `/`

Create `app/templates/base.html` — minimal page shell with htmx script tag, nav,
and content block.

Create `app/static/` directory (can be empty for now).

Add a CLI command (`cli/server.py`) or entry point to run the Flask dev server,
e.g., `uv run python -m cli serve`.

Verify the server starts and serves the base template at `http://localhost:5000/`.

### 6. Add API blueprint with core resource routes ✅

Implementation plan:
- Fill in `app/api/routes.py` with 6 read-only routes using `current_app.services`
- Serialize models inline (Account.to_dict(), Category/Transaction via helper)
- Error format: `{"error": "not_found"|"bad_request", "message": "..."}` with 400/404
- `GET /api/transactions/summary` registered before `<id>` to avoid route conflict
- Tests: Flask test client, fixtures create accounts/categories/transactions in DB

Create `app/api/__init__.py` and `app/api/routes.py`.

Register as a blueprint under `/api` in the app factory.

Implement these read-only routes to start:
- `GET /api/accounts` — list all accounts
- `GET /api/accounts/<id>` — single account
- `GET /api/categories` — list all categories
- `GET /api/transactions?month=YYYY/MM` — list transactions for a month
- `GET /api/transactions/<id>` — single transaction
- `GET /api/transactions/summary?start=YYYY/MM&end=YYYY/MM` — period summary

Each route should: get services from `current_app`, call the appropriate service
or data-layer method, and return `jsonify()` response. Follow the error format
from the architecture doc.

Add basic tests for the API routes using Flask's test client.

### 7. Add UI blueprint with htmx transaction views ✅

Implementation plan:
- Fill in `app/ui/routes.py` with 3 routes; `/ui/transactions` defaults to current month if no `?month=` given
- Fragment templates: transaction_list (table + prev/next month nav), account_list (table), category_list (table)
- `base.html` nav already has correct htmx links from item 5 — no change needed
- Tests: Flask test client checking status codes and key HTML strings

Create `app/ui/__init__.py` and `app/ui/routes.py`.

Register as a blueprint under `/ui` in the app factory.

Create templates in `app/templates/fragments/`:
- `transaction_list.html` — table of transactions for a month
- `account_list.html` — list of accounts
- `category_list.html` — list of categories

Implement routes:
- `GET /ui/transactions?month=YYYY/MM` — renders transaction list fragment
- `GET /ui/accounts` — renders account list fragment
- `GET /ui/categories` — renders category list fragment

Update `base.html` with navigation that uses `hx-get` to load these fragments.

CSS approach: use a classless CSS library (e.g., Simple.css or Pico CSS) for
baseline styling with no build step required.
