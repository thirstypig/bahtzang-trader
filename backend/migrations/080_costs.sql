-- Charter §4 cost tracking + backtester cost model.
-- Additive + nullable: safe to apply before the code that uses it deploys.
ALTER TABLE trades ADD COLUMN IF NOT EXISTS spread_cost NUMERIC(14,6) NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS fee_cost NUMERIC(14,6) NULL;

CREATE TABLE IF NOT EXISTS api_usage (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    portfolio_id INTEGER NULL REFERENCES portfolios(id) ON DELETE SET NULL,
    purpose VARCHAR(20) NOT NULL,
    model VARCHAR(64) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_input_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_input_tokens INTEGER NOT NULL DEFAULT 0,
    cost NUMERIC(12,6) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_api_usage_portfolio_ts ON api_usage (portfolio_id, timestamp);
