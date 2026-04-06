# TODO

Issues identified during code review, ordered by estimated effort (least to most).

## Quick fixes

- [x] **Add pydantic to dependencies** — `llm/providers/openai.py` imports pydantic but it's not in `pyproject.toml`; it only works transitively via the openai package.
  - **Plan**: Add `"pydantic>=2.0.0"` to `dependencies` in `pyproject.toml`, run `uv sync`, verify tests pass.

- [x] **Fix `total_changes` bug in `bulk_create`** — `services/transactions.py:140` uses `conn.total_changes` which counts all changes on the connection, not just the last `executemany`. Use `cursor.rowcount` instead.
  - **Plan**: Capture cursor from `conn.executemany(...)` and return `cursor.rowcount`. Add a test that verifies the count is correct when prior inserts exist on the same connection.

- [ ] **Enable foreign key enforcement** — `db/manager.py:33` opens SQLite connections without `PRAGMA foreign_keys = ON`, so all FK constraints (cascading deletes, referential integrity) are silently unenforced.

## Small changes

- [ ] **Remove dead `to_dict()` method** — `models/transaction.py:60` is unused (services build tuples directly), includes a stale `raw_data` field, and is missing newer fields like amortization and merchant name.

- [ ] **Rename `type` field on Transaction** — `models/transaction.py:18` shadows Python's builtin `type()`. Rename to `transaction_type` or similar across the codebase.

## Moderate refactors

- [ ] **Fix N+1 queries in `cmd_update_from_csv`** — `cli/transactions.py:416` does a `find()` per CSV row, then updates each transaction individually at line 545. Should batch-fetch transactions and group updates by field set.

- [ ] **Document or handle checksum collisions** — Transaction IDs are `sha256(csv_row)`. Two genuinely different transactions with identical CSV rows will silently collide. At minimum document the trade-off; ideally detect and warn.


## Larger efforts

- [ ] **Add test coverage for cli/, llm/, categorization.py, config.py** — These modules have zero test coverage and are excluded from CI coverage reporting. The CLI commands, LLM provider, prompt loader, and config loading are all untested.
