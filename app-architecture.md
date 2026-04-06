# Personal Python Service Architecture

## Design Philosophy

This document describes the architecture pattern for lightweight personal Python services (finance management, inventory, etc.). Each service follows the same structure: a core logic layer, a JSON API, and a server-rendered web UI — all served from a single process.

### Guiding Principles

- **Core logic is framework-agnostic.** Business logic knows nothing about HTTP, HTML, or Flask. It takes plain Python arguments and returns dataclasses or dicts. This is the same code the CLI calls.
- **The JSON API is a first-class citizen.** It is not a byproduct of the UI. It exists independently and is suitable for scripting, automation, and future integrations.
- **The web UI is a thin rendering layer.** It uses htmx to swap server-rendered HTML fragments, avoiding client-side JavaScript frameworks entirely. The UI calls the same core logic as the API — it does not call the API over HTTP.
- **No authentication or authorization.** Access control is handled externally (reverse proxy, network-level, etc.).
- **Minimal dependencies.** Flask for HTTP routing and Jinja2 templating. htmx (single script tag) for dynamic UI behavior. No JS build tooling, no bundlers, no client-side state management.

## Stack

| Layer | Technology | Role |
|-------|-----------|------|
| HTTP framework | Flask | Routing, request handling, JSON responses |
| Templating | Jinja2 (bundled with Flask) | Server-side HTML rendering |
| Frontend interactivity | htmx | HTML fragment swapping via AJAX, declared in HTML attributes |
| CSS | TBD (minimal, possibly classless) | Basic styling without a build step |
| Database | SQLite (typical) | Per-service persistent storage |
| CLI | Click or argparse | Command-line interface to core logic |

## Project Structure

```
my-service/
├── app/
│   ├── core/                  # Pure business logic — no HTTP, no HTML
│   │   ├── __init__.py
│   │   ├── models.py          # Dataclasses, types, domain objects
│   │   └── services.py        # Operations (CRUD, queries, transformations)
│   │
│   ├── api/                   # JSON API — Flask blueprint
│   │   ├── __init__.py
│   │   └── routes.py          # Routes under /api/, returns jsonify() responses
│   │
│   ├── ui/                    # Web UI — Flask blueprint, serves HTML for htmx
│   │   ├── __init__.py
│   │   └── routes.py          # Routes under /ui/, returns render_template() responses
│   │
│   ├── templates/
│   │   ├── base.html          # Full page shell: loads htmx, defines layout
│   │   └── fragments/         # Partial HTML snippets for htmx to swap in
│   │       └── expense_list.html
│   │
│   ├── static/                # CSS, htmx script, any minimal JS
│   │
│   └── app.py                 # Flask app factory, registers blueprints
│
├── cli.py                     # CLI entry point — calls core/ directly
├── pyproject.toml
└── README.md
```

### Key structural rules

- `core/` has **zero imports** from Flask, Jinja2, or any HTTP/web library.
- `api/routes.py` and `ui/routes.py` are thin wiring layers. Each route function should be a few lines: parse request args, call a core function, format the response.
- Templates in `fragments/` are **partial HTML**, not full pages. They render just the piece of the page that htmx will swap in.
- `base.html` is the only full-page template. It provides the shell (nav, htmx script tag, layout) and a content block that either loads a full page view or serves as the initial target for htmx swaps.

## How the Layers Interact

```
                    ┌──────────────┐
                    │  CLI (cli.py)│
                    └──────┬───────┘
                           │
                           ▼
┌─────────────┐    ┌──────────────┐    ┌───────────────────┐
│  JSON API   │───▶│  Core Logic  │◀───│  UI (htmx)        │
│  /api/*     │    │  core/       │    │  /ui/*            │
│             │    │              │    │                   │
│  returns    │    │  returns     │    │  returns rendered │
│  JSON       │    │  Python      │    │  HTML fragments   │
│             │    │  objects     │    │  via Jinja2       │
└─────────────┘    └──────────────┘    └───────────────────┘
```

Both the API and UI layers call core logic **directly as Python function calls**, not over HTTP. They diverge only in response format:

- **API route**: `return jsonify(get_expenses(category=cat))`
- **UI route**: `return render_template("fragments/expense_list.html", expenses=get_expenses(category=cat))`

## htmx Conventions

### How htmx works

htmx extends HTML with attributes that trigger HTTP requests and swap the response into the DOM. The server always returns rendered HTML — never JSON — to htmx endpoints.

```html
<!-- clicking this button GETs /ui/expenses?category=food -->
<!-- and swaps the response HTML into #expense-list -->
<button hx-get="/ui/expenses?category=food" hx-target="#expense-list">
  Show Food Expenses
</button>

<div id="expense-list">
  <!-- server-rendered fragment goes here -->
</div>
```

Core loop: **user interaction → HTTP request → server returns HTML fragment → htmx swaps it into the page.**

### Route naming

- `/api/*` — JSON API. Consumed by scripts, external tools, future integrations.
- `/ui/*` — HTML fragment endpoints. Consumed exclusively by htmx in the browser.
- `/` — Serves `base.html`, the page shell.

### Fragment design

Each htmx-targeted endpoint returns **only the HTML that needs to change**, not a full page. A fragment template like `fragments/expense_list.html` might look like:

```html
{% for e in expenses %}
<tr>
  <td>{{ e.category }}</td>
  <td>${{ "%.2f"|format(e.amount) }}</td>
  <td>
    <button hx-delete="/ui/expenses/{{ e.id }}" hx-target="closest tr" hx-swap="outerHTML">
      Delete
    </button>
  </td>
</tr>
{% endfor %}
```

### Forms and mutations

For create/update/delete operations, htmx submits forms or triggers requests with `hx-post`, `hx-put`, `hx-delete`. The UI route performs the mutation via core logic, then returns an updated HTML fragment (or an empty response with an `HX-Trigger` header to cause a refresh of a related element).

```html
<form hx-post="/ui/expenses" hx-target="#expense-list" hx-swap="beforeend">
  <input name="amount" type="number" step="0.01" required>
  <input name="category" type="text" required>
  <button type="submit">Add</button>
</form>
```

The corresponding UI route:

```python
@ui.route("/expenses", methods=["POST"])
def create_expense():
    expense = add_expense(
        amount=float(request.form["amount"]),
        category=request.form["category"],
    )
    return render_template("fragments/expense_row.html", e=expense)
```

## JSON API Conventions

### Response format

Successful responses return the resource directly:

```json
// GET /api/expenses
[
  {"id": 1, "amount": 42.50, "category": "food", "date": "2025-01-15"},
  {"id": 2, "amount": 15.00, "category": "transport", "date": "2025-01-16"}
]

// GET /api/expenses/1
{"id": 1, "amount": 42.50, "category": "food", "date": "2025-01-15"}

// POST /api/expenses (returns created resource)
{"id": 3, "amount": 22.00, "category": "utilities", "date": "2025-01-17"}
```

### Error format

Errors return a consistent structure:

```json
{
  "error": "not_found",
  "message": "Expense with id 99 does not exist"
}
```

With appropriate HTTP status codes (400, 404, 422, 500).

### Standard patterns

- `GET /api/<resource>` — list (supports query params for filtering)
- `GET /api/<resource>/<id>` — detail
- `POST /api/<resource>` — create (accepts JSON body)
- `PUT /api/<resource>/<id>` — update
- `DELETE /api/<resource>/<id>` — delete

## Flask App Factory Pattern

```python
# app/app.py
from flask import Flask

def create_app():
    app = Flask(__name__)

    from app.api.routes import api_bp
    from app.ui.routes import ui_bp

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(ui_bp, url_prefix="/ui")

    @app.route("/")
    def index():
        return render_template("base.html")

    return app
```

```python
# app/api/routes.py
from flask import Blueprint, jsonify, request
from app.core.services import get_expenses, add_expense

api_bp = Blueprint("api", __name__)

@api_bp.route("/expenses")
def list_expenses():
    category = request.args.get("category")
    return jsonify(get_expenses(category=category))

@api_bp.route("/expenses", methods=["POST"])
def create_expense():
    data = request.get_json()
    expense = add_expense(amount=data["amount"], category=data["category"])
    return jsonify(expense), 201
```

```python
# app/ui/routes.py
from flask import Blueprint, render_template, request
from app.core.services import get_expenses, add_expense

ui_bp = Blueprint("ui", __name__)

@ui_bp.route("/expenses")
def list_expenses():
    category = request.args.get("category")
    return render_template("fragments/expense_list.html", expenses=get_expenses(category=category))

@ui_bp.route("/expenses", methods=["POST"])
def create_expense():
    expense = add_expense(
        amount=float(request.form["amount"]),
        category=request.form["category"],
    )
    return render_template("fragments/expense_row.html", e=expense)
```

## Refactoring an Existing CLI Service

If the service already exists as a CLI, the migration path is:

1. **Extract core logic.** Move business logic out of CLI command handlers into `core/services.py`. CLI commands become thin wrappers that call core functions and format output for the terminal.
2. **Define data shapes.** Create dataclasses in `core/models.py` for the objects core functions return. These become the implicit contract for both JSON serialization and template rendering.
3. **Add the API layer.** Create `api/routes.py` with Flask routes that call core functions and `jsonify()` the results. Test with `curl`.
4. **Add the UI layer.** Create `base.html` and fragment templates. Add `ui/routes.py` with routes that call core functions and render fragments. Wire up htmx attributes in the HTML.
5. **Iterate.** Start with read-only views, then add forms for mutations.

## Open Decisions

_Track items here as they come up during implementation._

- **CSS approach**: classless CSS (e.g., Simple.css, Pico) vs. utility CSS vs. hand-rolled minimal stylesheet.
- **Error handling patterns**: how UI routes surface errors to the user (htmx response headers, inline error fragments, etc.).
- **Database access pattern**: whether core functions receive a db connection/session as an argument or manage it internally.
- **Configuration management**: environment variables, dotenv, or a config file per service.
- **Deployment**: how services are run in production (systemd, Docker, etc.).
