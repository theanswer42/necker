CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    period_type TEXT NOT NULL CHECK (period_type IN ('monthly', 'yearly')),
    amount INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id),
    UNIQUE (category_id, period_type)
);

CREATE INDEX IF NOT EXISTS idx_budgets_category_id ON budgets(category_id);
