-- Add auto_category_id column to transactions table
ALTER TABLE transactions ADD COLUMN auto_category_id INTEGER;

-- Create index for auto_category_id lookups
CREATE INDEX IF NOT EXISTS idx_transactions_auto_category_id ON transactions(auto_category_id);
