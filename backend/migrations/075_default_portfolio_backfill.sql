-- Migration: 075 — Default "Main" portfolio + backfill orphan trades
-- Context: Portfolio-only consolidation. Every trade must belong to a portfolio.
-- This migration:
-- 1. Creates a "Main" portfolio if none exist (preserves historical Alpaca state)
-- 2. Backfills trades.portfolio_id IS NULL → Main portfolio
-- 3. Adds NOT NULL constraint to trades.portfolio_id (final lockdown)
--
-- Idempotent: safe to re-run.

-- ============================================================
-- Step 1: Create Main portfolio if none exist
-- ============================================================
-- Uses INSERT ... SELECT WHERE NOT EXISTS to stay idempotent.
-- Budget defaults to 100000 placeholder; user adjusts via UI after migration.

INSERT INTO portfolios (
    name, budget, virtual_cash, trading_goal, risk_profile,
    trading_frequency, is_active,
    cooldown_hours, min_confidence, respect_wash_sale,
    kelly_fraction, circuit_breaker_daily_pct, circuit_breaker_weekly_pct,
    created_at, updated_at
)
SELECT
    'Main', 100000, 100000, 'maximize_returns', 'moderate',
    '1x', TRUE,
    48, 0.55, TRUE,
    0.15, -5.0, -10.0,
    NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM portfolios);

-- ============================================================
-- Step 2: Backfill orphan trades to the lowest-id active portfolio
-- ============================================================

UPDATE trades
SET portfolio_id = (
    SELECT id FROM portfolios
    WHERE is_active = TRUE
    ORDER BY id ASC
    LIMIT 1
)
WHERE portfolio_id IS NULL;

-- ============================================================
-- Step 3: Lock down — trades.portfolio_id is now mandatory
-- ============================================================
-- Only enforce NOT NULL if every row has a portfolio_id (i.e. backfill
-- succeeded). If there were no portfolios AND no trades, both steps are
-- no-ops and this constraint is the only lasting effect.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM trades WHERE portfolio_id IS NULL) THEN
        ALTER TABLE trades ALTER COLUMN portfolio_id SET NOT NULL;
    END IF;
END $$;
