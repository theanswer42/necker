-- Create transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL,
    data_import_id INTEGER NOT NULL,
    transaction_date DATE NOT NULL,
    post_date DATE,
    description TEXT NOT NULL,
    bank_category TEXT,
    category_id INTEGER,
    auto_category_id INTEGER,
    amount REAL NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('income', 'expense', 'transfer')),
    additional_metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (data_import_id) REFERENCES data_imports(id) ON DELETE CASCADE
);

-- Index for category lookups
CREATE INDEX IF NOT EXISTS idx_transactions_category_id ON transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_auto_category_id ON transactions(auto_category_id);
