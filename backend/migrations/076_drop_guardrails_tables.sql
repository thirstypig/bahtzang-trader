-- Migration: 076 — Drop guardrails_config + guardrails_audit tables
-- Context: Portfolio-only consolidation. Strategy lives on portfolios; rule-change
-- audit lives in portfolio_strategy_audit. The singleton guardrails_config table
-- and the global guardrails_audit log are obsolete.
--
-- IMPORTANT: irreversible. Take a backup before running.

DROP TABLE IF EXISTS guardrails_audit;
DROP TABLE IF EXISTS guardrails_config;
