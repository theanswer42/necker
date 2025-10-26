-- Create categories table for user-defined transaction categories
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for name lookups
CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name);
