-- Add merchant name fields to transactions table
ALTER TABLE transactions ADD COLUMN merchant_name TEXT;
ALTER TABLE transactions ADD COLUMN auto_merchant_name TEXT;

-- Index for merchant name lookups
CREATE INDEX IF NOT EXISTS idx_transactions_merchant_name ON transactions(merchant_name);
