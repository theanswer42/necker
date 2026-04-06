-- Rename accounts.type to accounts.account_type to avoid shadowing Python's builtin type()
ALTER TABLE accounts RENAME COLUMN type TO account_type;
