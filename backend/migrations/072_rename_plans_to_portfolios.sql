-- Migration: 072 — Rename plans to portfolios + add strategy columns
-- Context: Portfolio consolidation (Settings + Plans → unified Portfolio concept)
-- This migration:
-- 1. Renames plans table to portfolios
-- 2. Adds strategy columns (cooldown_hours, min_confidence, kelly_fraction, etc.)
-- 3. Updates all FK references (plans → portfolios)
-- 4. Updates all indexes
-- IMPORTANT: Take a backup before running.

-- ============================================================
-- Step 1: Rename plans table to portfolios
-- ============================================================

ALTER TABLE plans RENAME TO portfolios;

-- ============================================================
-- Step 2: Add strategy columns to portfolios
-- ============================================================

-- Per-ticker cooldown (hours, default 48)
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS cooldown_hours INTEGER DEFAULT 48 NOT NULL;

-- Minimum confidence threshold (0-1, stored as numeric for precision)
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS min_confidence NUMERIC(5,2) DEFAULT 0.55 NOT NULL;

-- Wash-sale compliance
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS respect_wash_sale BOOLEAN DEFAULT TRUE NOT NULL;

-- Kelly fraction for position sizing
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS kelly_fraction NUMERIC(3,2) DEFAULT 0.15 NOT NULL;

-- Circuit breaker: daily loss threshold (%)
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS circuit_breaker_daily_pct NUMERIC(5,2) DEFAULT -5.0 NOT NULL;

-- Circuit breaker: weekly loss threshold (%)
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS circuit_breaker_weekly_pct NUMERIC(5,2) DEFAULT -10.0 NOT NULL;

-- ============================================================
-- Step 3: Update ForeignKey references
-- ============================================================

-- plan_snapshots.plan_id → portfolio_id
ALTER TABLE plan_snapshots RENAME COLUMN plan_id TO portfolio_id;
ALTER TABLE plan_snapshots DROP CONSTRAINT plan_snapshots_plan_id_fkey;
ALTER TABLE plan_snapshots ADD CONSTRAINT plan_snapshots_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE;

-- trades.plan_id → portfolio_id
ALTER TABLE trades RENAME COLUMN plan_id TO portfolio_id;
-- Note: trades.plan_id had ON DELETE RESTRICT (intentionally); keep that behavior
ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_plan_id_fkey;
ALTER TABLE trades ADD CONSTRAINT trades_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE RESTRICT;

-- ============================================================
-- Step 4: Rename and update indexes
-- ============================================================

-- Drop old indexes on trades
DROP INDEX IF EXISTS ix_trades_plan_timestamp;
DROP INDEX IF EXISTS ix_trades_plan_ticker;
DROP INDEX IF EXISTS ix_trades_plan_executed;

-- Create new indexes with portfolio naming
CREATE INDEX IF NOT EXISTS ix_trades_portfolio_timestamp ON trades (portfolio_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_trades_portfolio_ticker ON trades (portfolio_id, ticker, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_trades_portfolio_executed ON trades (portfolio_id, executed, timestamp DESC);

-- Update plan_snapshots indexes
DROP INDEX IF EXISTS ix_plan_snapshots_plan_date;
CREATE INDEX IF NOT EXISTS ix_portfolio_snapshots_portfolio_date ON plan_snapshots (portfolio_id, date DESC);

-- ============================================================
-- Step 5: Verify migration
-- ============================================================

-- Check plans renamed:
-- SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'portfolios');

-- Check plans no longer exists:
-- SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'plans');

-- Check new columns exist:
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'portfolios' AND column_name IN ('cooldown_hours', 'min_confidence', 'kelly_fraction');

-- Check ForeignKey references updated:
-- SELECT constraint_name, table_name, column_name FROM information_schema.constraint_column_usage WHERE table_name IN ('plan_snapshots', 'trades') AND column_name = 'portfolio_id';
