-- Risk engine: track the broker-held stop attached to a trade row so the executor can
-- reconcile fired stops, cancel its own stop before a sell, and flag unprotected
-- positions. Additive + nullable: safe to apply before the code that reads it deploys.
ALTER TABLE trades ADD COLUMN IF NOT EXISTS stop_price NUMERIC(14,4) NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS stop_order_id VARCHAR(64) NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS stop_state VARCHAR(16) NULL;
