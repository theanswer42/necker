-- Add parent_id to categories table for hierarchical categories
ALTER TABLE categories ADD COLUMN parent_id INTEGER REFERENCES categories(id);

-- Index for parent lookups
CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories(parent_id);
