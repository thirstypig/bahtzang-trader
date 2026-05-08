-- Migration: 074 — Create portfolio_strategy_audit table
-- Context: Audit log for strategy rule changes (cooldown, confidence, frequency caps, etc.)
-- Tracks: who changed what, when, and why
-- Enables users to correlate rule changes with trade performance

-- ============================================================
-- Create portfolio_strategy_audit table
-- ============================================================

CREATE TABLE IF NOT EXISTS portfolio_strategy_audit (
    id BIGSERIAL PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    user_email VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ============================================================
-- Create indexes
-- ============================================================

-- Fast query by portfolio + timestamp (most common audit log view)
CREATE INDEX IF NOT EXISTS ix_portfolio_strategy_audit_portfolio_timestamp
    ON portfolio_strategy_audit (portfolio_id, timestamp DESC);

-- Fast lookup by action type (for filtering by rule type)
CREATE INDEX IF NOT EXISTS ix_portfolio_strategy_audit_action
    ON portfolio_strategy_audit (portfolio_id, action, timestamp DESC);

-- Fast lookup by user (for accountability)
CREATE INDEX IF NOT EXISTS ix_portfolio_strategy_audit_user
    ON portfolio_strategy_audit (user_email, timestamp DESC);

-- ============================================================
-- Verify migration
-- ============================================================

-- Check table created:
-- SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'portfolio_strategy_audit');

-- Check indexes:
-- SELECT indexname FROM pg_indexes WHERE tablename = 'portfolio_strategy_audit';
