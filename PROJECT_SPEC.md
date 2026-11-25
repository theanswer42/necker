# Project spec: necker

Status: approved 2026-11-23. Built against `toolshed/python/working-with-agents.md`.

## Purpose

Necker is a personal finance tool for one user. It imports transactions from bank and credit card CSV exports, helps the user categorize them (with deterministic rules and an LLM), and reports where money went each month: income, spending by category, savings, and progress against budgets. Reports are not live. Correctness of past months matters more than freshness.

Non-goals: multi-user, authentication, connecting to banks, multi-currency (everything is USD), net worth or balance tracking, live or pending-transaction views.

## Entities

| Entity | Description | Key fields | Relations |
| --- | --- | --- | --- |
| Account | A bank or card account the user exports CSVs from | `name` (unique, `[a-z_]+`), `institution` (parser key: `bofa`, `bofacc`, `chase`, `amex`, `discover`), `role` (`spending` \| `tracking`), `description` | Has many DataImports and Transactions |
| DataImport | One CSV file imported into one account | `file_sha256` (unique), `original_filename`, `archive_path`, `imported_at`, counts: `parsed`, `inserted`, `duplicates`, `pending_skipped` | Belongs to Account. Has many Transactions |
| Transaction | One row from a bank export, as the bank stated it. Immutable after import | `dedup_key`, `date`, `date_source` (`transaction` \| `posted`), `post_date` (nullable), `description`, `amount` (signed integer cents), `bank_category` (nullable), `bank_metadata` (JSON, nullable) | Belongs to Account and DataImport. Has zero or one Review, zero or more Allocations, zero or one Suggestion |
| Review | The user's decision about a transaction | `reviewed_at`, `merchant_name` (nullable), `note` (nullable) | Belongs to Transaction (one-to-one) |
| Allocation | A piece of a transaction's amount assigned to a category and a month | `category_id`, `amount` (signed integer cents), `period` (calendar month) | Belongs to Transaction and to a leaf Category |
| Category | A classification for allocations, in a tree | `name` (unique), `parent_id` (nullable), `kind` (`income` \| `expense` \| `savings` \| `transfer`) | Parent Category. Child Categories. Allocations only on leaves |
| Suggestion | The latest proposal for a transaction, from a rule or the LLM. Its existence marks the transaction as categorized | `source` (`rule` \| `llm`), `rule_id` (set when source is `rule`), `category_id` (nullable), `merchant_name` (nullable), `model` and `prompt_version` (set when source is `llm`), `created_at` | Belongs to Transaction (one per transaction, replaced on re-run) |
| Rule | A deterministic categorization rule, applied before the LLM | `match` (case-insensitive substring of `description`), `account_id` (nullable = any account), `category_id`, `priority` | Points at a leaf Category |
| Budget | For an expense category, a limit (maximum) over a period. For a savings category, a target (minimum) | `category_id`, `period_type` (`monthly` \| `yearly`), `amount` (positive integer cents) | Belongs to an expense or savings Category (any level; includes descendants) |

### Terms

- **Sign convention.** Negative means money leaving the user, positive means money coming in, for every account and institution. A card purchase is negative; a card refund or payment received is positive.
- **Cash view.** Allocations grouped by the month of their transaction's `date`. Answers "what went out this month".
- **Smoothed view.** Allocations grouped by their `period`. Answers "what this month cost". Budgets use this view.
- **Outflow.** Expense and savings totals are reported as the negated sum of their allocations, so purchases count up and refunds count down.
- **Periods.** Reports cover calendar months. A yearly budget covers a calendar year.
- **Leaf.** A category with no children.

## State machines

| Entity | From | Event | To | Condition |
| --- | --- | --- | --- | --- |
| Transaction | (none) | import | uncategorized | Row parsed; `(account, dedup_key)` not already present |
| Transaction | uncategorized | categorize | categorized | A rule matched, or the LLM returned a result for it (even one without a category). A Suggestion is written |
| Transaction | categorized | review | reviewed | Allocations given satisfy INV-10, INV-12, INV-14, INV-28; Review and Allocations written in one DB transaction |
| Transaction | reviewed | edit | reviewed | Allocations replaced as a whole, still satisfying INV-10, INV-12, INV-14, INV-28 |
| DataImport | (none) | import | in review | File hash not seen before; every row parsed |
| DataImport | in review | last transaction reviewed | complete | Derived, not stored: complete when it has no unreviewed transactions |
| DataImport | in review or complete | delete | (none) | User confirms; see INV-9 |

Uncategorized and categorized transactions are both unreviewed. There is no transition from reviewed back to unreviewed. Categorization runs per transaction, whatever import it came from. While the LLM provider is unavailable, transactions that no rule matches stay uncategorized and cannot be reviewed. Waiting for the provider is deliberate: ingests are infrequent and reports are not time-critical.

## Invariants

IDs were renumbered by section before approval. They are stable from approval on.

### Import (T1)

| ID | Statement | Tier | Enforced in | Property |
| --- | --- | --- | --- | --- |
| INV-1 | Every transaction amount follows the sign convention, for every institution. | T1 | core (per-institution parser) | tests/properties/test_inv_1_sign_convention |
| INV-2 | Amounts are exact integer cents. An amount with more than two decimal places is rejected, never rounded. | T1 | core, schema (INTEGER) | tests/properties/test_inv_2_exact_cents |
| INV-3 | A malformed row fails the whole import with the row number and reason. Pending rows, where an export marks them, are skipped and counted, not stored. | T1 | core | tests/properties/test_inv_3_malformed_fails |
| INV-4 | The dedup key is a hash of (date, amount, description trimmed and uppercased) plus the occurrence ordinal of that triple within its file. Importing files with overlapping rows, in any order, stores each distinct row once, and keeps genuinely repeated rows that appear within one file. | T1 | core | tests/properties/test_inv_4_dedup, reference model |
| INV-5 | Within an account, each dedup key appears at most once. | T1 | schema UNIQUE(account_id, dedup_key) | tests/repos/test_inv_5_unique_dedup |
| INV-6 | A file whose SHA-256 matches an existing import is rejected, naming that import. | T1 | schema UNIQUE(file_sha256), service | tests/properties/test_inv_6_same_file |
| INV-7 | An import is atomic: either the DataImport and all its transactions are stored, or nothing is, and no archive file is left behind. | T1 | service (transaction helper) | tests/properties/test_inv_7_atomic_import |
| INV-8 | A transaction's imported fields never change after import. | T1 | schema (BEFORE UPDATE trigger), repos (no UPDATE statement) | tests/repos/test_inv_8_immutable |
| INV-27 | For every import, `parsed` equals `inserted` plus `duplicates`. Pending rows are counted separately in `pending_skipped` and are not part of `parsed`. | T1 | core, service | tests/properties/test_inv_27_import_counts |
| INV-9 | Deleting an import removes its DataImport record, transactions, reviews, allocations and suggestions in one DB transaction, then its archive file. Afterwards the same file can be imported again. No other code path deletes transactions. The confirmation states how many transactions are reviewed, and that rows other imports also contained are removed with it. | T1 | service, schema (FK RESTRICT, no cascades) | tests/properties/test_inv_9_delete_import |

### Review and allocation (T1)

| ID | Statement | Tier | Enforced in | Property |
| --- | --- | --- | --- | --- |
| INV-10 | A reviewed transaction's allocations sum exactly to its amount. | T1 | core, service | tests/properties/test_inv_10_allocations_sum_to_amount |
| INV-11 | A transaction has a Review if and only if it has at least one Allocation. | T1 | core, service (one DB transaction) | tests/properties/test_inv_11_reviewed_iff_allocated |
| INV-12 | Allocations reference only leaf categories. | T1 | core, service | tests/properties/test_inv_12_leaf_only |
| INV-13 | Amortizing amount A over N months from month M produces N allocations in consecutive months M to M+N−1. Each of the first N−1 has A divided by N truncated toward zero, the last holds the remainder, and they sum to A. | T1 | core | tests/properties/test_inv_13_amortization |
| INV-28 | Every allocation is non-zero and has the same sign as its transaction. A zero-amount transaction has exactly one zero allocation. | T1 | core | tests/properties/test_inv_28_allocation_sign |
| INV-14 | Only expense-kind allocations may fall in a month other than their transaction's month. | T1 | core | tests/properties/test_inv_14_amortize_expense_only |

### Categories (T2)

| ID | Statement | Tier | Enforced in | Property |
| --- | --- | --- | --- | --- |
| INV-15 | The category tree has no cycles, and a child has the same kind as its parent. | T2 | core, service | tests/properties/test_inv_15_tree |
| INV-16 | A category that has allocations or rules cannot gain children. Moving them to a leaf comes first. | T2 | service | tests/properties/test_inv_16_no_children_on_used |
| INV-17 | A category with children, allocations, rules, or budgets cannot be deleted. | T2 | schema (FK RESTRICT), service | tests/repos/test_inv_17_category_delete |
| INV-29 | An account that has imports cannot be deleted. | T2 | schema (FK RESTRICT), service | tests/repos/test_inv_29_account_delete |

### Reports (T2)

| ID | Statement | Tier | Enforced in | Property |
| --- | --- | --- | --- | --- |
| INV-18 | The smoothed view and the cash view of the same allocations have the same total over all time. | T2 | core | tests/properties/test_inv_18_views_agree |
| INV-19 | Report totals per kind count only allocations of reviewed transactions in spending accounts. Transfer-kind allocations are excluded from income, expense, and savings. | T2 | core, repos | tests/properties/test_inv_19_report_scope, reference model |
| INV-20 | A parent category's total in any view equals the sum of its descendants' totals. | T2 | core | tests/properties/test_inv_20_rollup |
| INV-21 | A report for a period states how many unreviewed spending-account transactions are dated on or before the period's end, and is marked incomplete when that number is not zero. | T2 | core, UI | tests/properties/test_inv_21_incomplete_flag |
| INV-22 | A budget's actual equals the smoothed-view outflow of its category and descendants for the period. An expense budget is over when actual exceeds amount. A savings budget is met when actual reaches amount. Budgets exist only on expense or savings categories. | T2 | core | tests/properties/test_inv_22_budget_actual |

### Categorization (T2)

| ID | Statement | Tier | Enforced in | Property |
| --- | --- | --- | --- | --- |
| INV-23 | Rules and suggestions never write Reviews or Allocations. They only prefill what the user confirms. | T2 | services | tests/properties/test_inv_23_suggest_only |
| INV-24 | A suggestion naming an unknown or non-leaf category is stored without a category and logged, never raised to the user as valid. | T2 | core | tests/properties/test_inv_24_suggestion_validation |
| INV-25 | When rules match, the highest-priority rule decides, its suggestion has source `rule`, and the LLM is not asked about that transaction. | T2 | core | tests/properties/test_inv_25_rule_priority |
| INV-26 | A transaction can be reviewed only once it has a Suggestion. | T2 | service | tests/properties/test_inv_26_review_needs_suggestion |

## Risk tiers

| Concept or module | Tier | Reason |
| --- | --- | --- |
| CSV parsing and sign normalization | T1 | A wrong sign or a dropped row corrupts every report silently |
| Deduplication, import atomicity, import deletion | T1 | Duplicates or lost rows are silent |
| Allocations, amortization, review persistence | T1 | Money assignment. Errors are silent |
| Schema, migrations, snapshot, admin commands | T1 | Data integrity, irreversible |
| Secrets handling (API key) | T1 | Principle 15 |
| Reports and budget aggregation | T2 | Visible in the UI and recoverable, since raw data is untouched |
| Category tree | T2 | Visible, recoverable |
| Rules, LLM prompt building and response parsing | T2 | Output is reviewed by the user before it counts |
| LLM HTTP client | T3 | Shell. Failures are visible as missing suggestions |
| Web routes, templates, app CSS | T3 | Plumbing and UI |

## Reference models

- **Import model** (`tests/models/imports.py`): a dict keyed by account of multisets of (date, amount, normalized description). Hypothesis runs sequences of file imports, including overlapping and repeated files, against the real service and the model, and compares stored rows. Covers INV-4 to INV-7, INV-9 and INV-27.
- **Report model** (`tests/models/reports.py`): plain Python loops over all transactions and allocations to compute the cash and smoothed totals per category and kind. Used as the oracle for the SQL-backed report queries. Covers INV-18 to INV-20 and INV-22.

## Runtime

- Network tier: `allowlisted`. Only the configured LLM provider is reached.
- Egress allowlist: `api.anthropic.com`. It changes when another provider is added.
- Ports: web 8000 (`/ui`, `/api`, `/health`).
- Secrets: `ANTHROPIC_API_KEY` (file via `ANTHROPIC_API_KEY_FILE`), for LLM categorization. Optional: the app starts without it.
- Settings: `DATA_DIR`, `LOG_LEVEL`, `ALLOWED_HOSTS`, `LLM_PROVIDER` (`anthropic`, or `fake` in development only), `LLM_MODEL`, `CATEGORIZATION_BATCH_SIZE`.
- LLM categorization has no on/off switch. Only the provider and model are configurable. The app starts and serves `/health` without a working provider. Import and rules still run, and the UI shows a banner naming the problem (no key, key rejected, provider unreachable), which is also logged at `error`. Transactions waiting on the LLM can be retried from the import's review page. Tests use a fake provider passed in through `create_app`, never a setting.
- The `fake` provider makes no network calls and returns made-up suggestions (a random leaf category, sometimes none), so the review flow can be exercised without a key. `make dev` and `make seed` default to it when no key is set. `serve.py` refuses to start with `LLM_PROVIDER=fake`, and a test checks this.
- State under `/data`: the database, `backups/` (pre-migration and manual snapshots), `archives/` (gzipped copies of every imported CSV).
- No sessions and no Flask `SECRET_KEY`. Request safety follows the base spec's header rules.

## UI

The UI follows `toolshed/design_guide` (`GUIDE.md` for layout, components and interaction rules). There is no CSS build step and no Tailwind.

- **Vendored files.** `design.css`, `design.js`, `themes.css` and `fonts/` are copied unchanged into `src/necker/web/static/design/`. Each keeps its `version:` header line (currently `design.css` 0.3.1, `design.js` 0.2.0, `themes.css` 0.2.0). They are never edited in this repo: updating means copying a newer version from toolshed. Formatting hooks and linters skip that directory.
- **App CSS.** `static/app.css` holds necker-specific rules inside `@layer app { … }`, using tokens only. A test fails if `app.css` contains a raw colour value (hex, `rgb()`, `hsl()`, `oklch()`). A missing token is added to the design guide, not worked around here.
- **Theme.** `sepia`, set with `<html data-theme="sepia">`, which loads `themes.css`. Light and dark follow the system setting.
- **Pages.** Each page uses one of the guide's page types:

| Page | Guide page type | Notes |
| --- | --- | --- |
| Accounts, Categories, Rules, Budgets | Collection (table view) | Add via form page or inline form. Deletes go through the confirm dialog |
| Import (upload) | Form page | Account picker and file input |
| Imports | Collection (list view) | Each import shows counts (INV-27) and its review progress |
| Import review | Bulk edit | Suggested values shown as `<em class="muted">` until confirmed. Sticky footer bar with the single save. `.alert.warning` while the LLM provider is unavailable |
| Transaction | Detail | `dl.kv` with the imported fields (read-only), plus the allocation editor (splits, amortization) as a form |
| Reports | App-specific, in the standard shell | Month `.pager` in the toolbar, cash or smoothed as a `.segmented` view switcher, tabs for Summary, By category and Transactions. `.alert.warning` when the report is incomplete (INV-21) |

- **Feedback.** Every mutation ends with a flash, swapped out-of-band into `#flash`, or with inline errors (`.field-error`, `aria-invalid`). Deleting an import uses the confirm dialog, and its message carries the counts INV-9 requires.

## External consumers

None yet. The JSON API is intended for a future personal-assistant agent. Listing it here will make `docs/openapi.yaml` required.

| Consumer | Interface | Docs |
| --- | --- | --- |

## Deviations from the base spec

- **Admin CLI.** `src/necker/admin.py` (argparse) provides `migrate status`, `migrate apply`, `snapshot [path]`, and `reset` (refuses to run outside `.data/`). It runs only inside the container (`docker exec`) or against `.data/` in development. Reason: these operations are destructive or expose all data, and the app has no authentication, so they are never exposed over HTTP. `migrate apply` calls the same function as `serve.py`. `docs/cli.md` is generated from `--help` by `make docs` and checked by a test (a nice-to-have, but cheap for so few commands).
- **LLM provider interface.** `clients/llm/` defines a provider protocol with an Anthropic implementation over httpx and a development-only `fake`, selected by `LLM_PROVIDER`. Reason: the user plans to try other providers (Gemini, local models). Prompt building and response parsing live in the core and do not depend on the provider.

## Open questions

1. **Pending transactions.** It's unknown whether any export includes pending rows, and how each would mark them. Current plan: skip and count them. Warn when a pending row is older than some threshold, so the user can re-export later.
2. **Rule matching.** Is a case-insensitive substring enough, or are prefix and regex matches needed? Should accepting a suggestion offer to create a rule? Note for the task that settles this: there are plenty of sample CSVs to decide from by looking at real descriptions. They are in the gitignored `samples/` directory, so they must be made available to the agent doing the task.

## Change log

| Date | Change | Approved by |
| --- | --- | --- |
| 2026-11-23 | Initial spec for the v2 rebuild | Sagar |
| 2026-11-25 | Replace Tailwind with `toolshed/design_guide`; add the UI section | pending |
