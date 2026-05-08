-- Migration: 073 — Create portfolio_touch_history table
-- Context: Track per-ticker touch timestamps to enforce cooldown rules
-- Tracks: last_decision_timestamp and last_action per ticker per portfolio
-- Used by: Trading constraints checker to prevent repetitive trading on same ticker

-- ============================================================
-- Create portfolio_touch_history table
-- ============================================================

CREATE TABLE IF NOT EXISTS portfolio_touch_history (
    id BIGSERIAL PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    last_decision_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    last_action VARCHAR(10) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ============================================================
-- Create indexes
-- ============================================================

-- Fast lookup by portfolio + ticker (for cooldown checks)
CREATE UNIQUE INDEX IF NOT EXISTS ix_portfolio_touch_history_portfolio_ticker
    ON portfolio_touch_history (portfolio_id, ticker);

-- Fast query by portfolio (for debugging / audit)
CREATE INDEX IF NOT EXISTS ix_portfolio_touch_history_portfolio
    ON portfolio_touch_history (portfolio_id, ticker, last_decision_timestamp DESC);

-- ============================================================
-- Verify migration
-- ============================================================

-- Check table created:
-- SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'portfolio_touch_history');

-- Check indexes:
-- SELECT indexname FROM pg_indexes WHERE tablename = 'portfolio_touch_history';
