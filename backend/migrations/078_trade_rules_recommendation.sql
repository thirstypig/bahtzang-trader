-- Add rules_recommendation to trades for rules_with_claude_oversight mode.
-- Stores the strategy's original signal before Claude review so we can later
-- measure strategy-vs-Claude divergence and tune the strategy or oversight prompt.
ALTER TABLE trades ADD COLUMN IF NOT EXISTS rules_recommendation JSON NULL;
