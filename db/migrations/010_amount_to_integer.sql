-- Migrate amount column from REAL to INTEGER (cents) to avoid floating-point rounding errors.
-- $5.75 is stored as 575, $100.00 as 10000, etc.
ALTER TABLE transactions RENAME COLUMN amount TO amount_real;
ALTER TABLE transactions ADD COLUMN amount INTEGER NOT NULL DEFAULT 0;
UPDATE transactions SET amount = CAST(ROUND(amount_real * 100) AS INTEGER);
ALTER TABLE transactions DROP COLUMN amount_real;
