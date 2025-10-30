-- Add amortization fields to transactions table
ALTER TABLE transactions ADD COLUMN amortize_months INTEGER;
ALTER TABLE transactions ADD COLUMN amortize_end_date DATE;

-- Index for amortization queries
CREATE INDEX IF NOT EXISTS idx_transactions_amortize_end_date ON transactions(amortize_end_date);
