-- Charter DOC-054 (simplified 2026-11-09): two Claude strategies, $10k paper each,
-- identical except risk_profile (which sets bet sizes via risk.PROFILE_LIMITS and
-- Claude's style via RISK_PROMPTS). Both read the screener's top 25 each morning.
-- Idempotent: refuses to run if either name already exists.
BEGIN;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM portfolios WHERE name IN ('Conservative', 'Aggressive')) THEN
    RAISE EXCEPTION 'Conservative/Aggressive portfolios already exist';
  END IF;
END $$;

INSERT INTO portfolios (
  name, budget, virtual_cash, trading_goal, risk_profile, trading_frequency,
  is_active, cooldown_hours, min_confidence, respect_wash_sale, kelly_fraction,
  circuit_breaker_daily_pct, circuit_breaker_weekly_pct, created_at, updated_at,
  decision_mode, strategy_id, strategy_params
) VALUES
  ('Conservative', 10000, 10000, 'beat_sp500', 'conservative', '1x',
   true, 48, 0.55, true, 0.15, -5.0, -10.0, now(), now(),
   'claude_decides', NULL, '{"screener_top_n": 25}'),
  ('Aggressive', 10000, 10000, 'beat_sp500', 'aggressive', '1x',
   true, 48, 0.55, true, 0.15, -5.0, -10.0, now(), now(),
   'claude_decides', NULL, '{"screener_top_n": 25}');

SELECT id, name, risk_profile, budget, is_active, strategy_params FROM portfolios
WHERE name IN ('Conservative', 'Aggressive') ORDER BY id;
COMMIT;
