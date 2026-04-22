-- Migration: 067 (Unify Trade + PlanTrade) + 071 (Float → Numeric)
-- Run this on the production Supabase PostgreSQL database.
-- IMPORTANT: Take a backup before running.
--
-- This migration:
-- 1. Adds plan-specific columns to the trades table
-- 2. Converts money columns from FLOAT to NUMERIC(14,4)
-- 3. Copies all plan_trades data into trades
-- 4. Drops the plan_trades table
-- 5. Adds plan-scoped indexes

-- ============================================================
-- Step 1: Add plan columns to trades table
-- ============================================================

ALTER TABLE trades ADD COLUMN IF NOT EXISTS plan_id INTEGER REFERENCES plans(id) ON DELETE RESTRICT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS alpaca_order_id VARCHAR(64);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS virtual_cash_before NUMERIC(14,4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS virtual_cash_after NUMERIC(14,4);

-- Step 2: Change quantity from INTEGER to FLOAT (fractional shares)
ALTER TABLE trades ALTER COLUMN quantity TYPE DOUBLE PRECISION USING quantity::DOUBLE PRECISION;

-- Step 3: Convert money columns to NUMERIC(14,4)
ALTER TABLE trades ALTER COLUMN price TYPE NUMERIC(14,4) USING price::NUMERIC(14,4);

ALTER TABLE plans ALTER COLUMN budget TYPE NUMERIC(14,4) USING budget::NUMERIC(14,4);
ALTER TABLE plans ALTER COLUMN virtual_cash TYPE NUMERIC(14,4) USING virtual_cash::NUMERIC(14,4);
ALTER TABLE plans ALTER COLUMN target_amount TYPE NUMERIC(14,4) USING target_amount::NUMERIC(14,4);

ALTER TABLE plan_snapshots ALTER COLUMN budget TYPE NUMERIC(14,4) USING budget::NUMERIC(14,4);
ALTER TABLE plan_snapshots ALTER COLUMN virtual_cash TYPE NUMERIC(14,4) USING virtual_cash::NUMERIC(14,4);
ALTER TABLE plan_snapshots ALTER COLUMN invested_value TYPE NUMERIC(14,4) USING invested_value::NUMERIC(14,4);
ALTER TABLE plan_snapshots ALTER COLUMN total_value TYPE NUMERIC(14,4) USING total_value::NUMERIC(14,4);
ALTER TABLE plan_snapshots ALTER COLUMN pnl TYPE NUMERIC(14,4) USING pnl::NUMERIC(14,4);
ALTER TABLE plan_snapshots ALTER COLUMN pnl_pct TYPE NUMERIC(10,4) USING pnl_pct::NUMERIC(10,4);

ALTER TABLE portfolio_snapshots ALTER COLUMN total_equity TYPE NUMERIC(14,4) USING total_equity::NUMERIC(14,4);
ALTER TABLE portfolio_snapshots ALTER COLUMN cash TYPE NUMERIC(14,4) USING cash::NUMERIC(14,4);
ALTER TABLE portfolio_snapshots ALTER COLUMN invested TYPE NUMERIC(14,4) USING invested::NUMERIC(14,4);
ALTER TABLE portfolio_snapshots ALTER COLUMN unrealized_pnl TYPE NUMERIC(14,4) USING unrealized_pnl::NUMERIC(14,4);
ALTER TABLE portfolio_snapshots ALTER COLUMN spy_close TYPE NUMERIC(14,4) USING spy_close::NUMERIC(14,4);
ALTER TABLE portfolio_snapshots ALTER COLUMN deposit_withdrawal TYPE NUMERIC(14,4) USING deposit_withdrawal::NUMERIC(14,4);

ALTER TABLE guardrails_config ALTER COLUMN max_total_invested TYPE NUMERIC(14,4) USING max_total_invested::NUMERIC(14,4);
ALTER TABLE guardrails_config ALTER COLUMN max_single_trade_size TYPE NUMERIC(14,4) USING max_single_trade_size::NUMERIC(14,4);

-- ============================================================
-- Step 4: Copy plan_trades into trades (if plan_trades exists)
-- ============================================================

INSERT INTO trades (
    timestamp, ticker, action, quantity, price,
    claude_reasoning, confidence, guardrail_passed, guardrail_block_reason,
    executed, plan_id, alpaca_order_id, virtual_cash_before, virtual_cash_after
)
SELECT
    timestamp, ticker, action, quantity, price,
    claude_reasoning, confidence, guardrail_passed, guardrail_block_reason,
    executed, plan_id, alpaca_order_id, virtual_cash_before, virtual_cash_after
FROM plan_trades;

-- ============================================================
-- Step 5: Drop plan_trades table
-- ============================================================

DROP TABLE IF EXISTS plan_trades;

-- ============================================================
-- Step 6: Add plan-scoped indexes on trades
-- ============================================================

CREATE INDEX IF NOT EXISTS ix_trades_plan_timestamp ON trades (plan_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_trades_plan_ticker ON trades (plan_id, ticker, timestamp);
CREATE INDEX IF NOT EXISTS ix_trades_plan_executed ON trades (plan_id, executed, timestamp);

-- ============================================================
-- Verification queries (run these to confirm migration worked)
-- ============================================================

-- Check plan trades were copied:
-- SELECT COUNT(*) FROM trades WHERE plan_id IS NOT NULL;

-- Check no plan_trades table remains:
-- SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'plan_trades');

-- Check column types:
-- SELECT column_name, data_type, numeric_precision, numeric_scale
-- FROM information_schema.columns
-- WHERE table_name = 'trades' AND column_name IN ('price', 'quantity', 'virtual_cash_before');
