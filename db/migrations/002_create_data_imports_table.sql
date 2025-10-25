-- Create data_imports table to track CSV import operations
CREATE TABLE data_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    filename TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

-- Create index for faster lookups by account
CREATE INDEX idx_data_imports_account_id ON data_imports(account_id);
