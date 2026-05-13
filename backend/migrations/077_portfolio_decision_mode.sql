-- Add decision_mode, strategy_id, strategy_params to portfolios.
-- decision_mode controls who drives trade decisions for a portfolio:
--   claude_decides              — Claude makes all buy/sell/hold calls (default, existing behavior)
--   rules_decide                — deterministic strategy; Claude not called
--   rules_with_claude_oversight — strategy recommends, Claude reviews
ALTER TABLE portfolios
    ADD COLUMN IF NOT EXISTS decision_mode VARCHAR(32) NOT NULL DEFAULT 'claude_decides',
    ADD COLUMN IF NOT EXISTS strategy_id VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS strategy_params JSON NOT NULL DEFAULT '{}';
