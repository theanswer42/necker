-- Track whether a transaction has been through the per-import review flow.
ALTER TABLE transactions ADD COLUMN import_reviewed BOOLEAN NOT NULL DEFAULT 0;

-- Existing transactions are de-facto reviewed (they predate this flow);
-- mark them so they don't surface as incomplete imports.
UPDATE transactions SET import_reviewed = 1;

-- Index supports the "next unreviewed batch for this import" query.
CREATE INDEX IF NOT EXISTS idx_transactions_import_review
  ON transactions(data_import_id, import_reviewed);
