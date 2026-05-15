---
name: crypto-symbols-in-stock-pipeline
description: BTC and ETH were included in GOAL_PROMPTS for maximize_returns and swing_trading goals, but the price pipeline uses Alpaca's StockHistoricalDataClient (stocks only). BTC resolved to a ~$35 stock instrument, causing Claude to recommend sub-$1 micro-trades that were blocked every scheduler run by the minimum trade value guardrail.
type: logic-error
severity: high
component:
  - backend/app/claude_brain.py
  - backend/app/technical_analysis.py
tags: [alpaca, crypto, guardrails, goal-prompts, scheduler, paper-trading, data-pipeline, silent-failure]
date: 2026-05-14
status: resolved
---

# Crypto Tickers in Stock Data Client — Silent Wrong Price, Guardrail Block Every Cycle

## Problem

Every scheduler run, BTC buy decisions were silently blocked with "Trade value $0.35 below $1 minimum." No error was raised, no alert fired — the block was logged as a normal guardrail rejection and the cycle moved on. Over time this accumulated to 160 blocked trades in production, burning Claude decision slots without executing anything.

## How It Was Discovered

A distribution query on the `trades` table surfaced the pattern:

```sql
SELECT guardrail_block_reason, COUNT(*)
FROM trades
WHERE executed = false AND action = 'buy'
GROUP BY guardrail_block_reason
ORDER BY count DESC;
```

Result: 156 rows with `"Trade value $$0.35 below $1 minimum"` for BTC buys, plus 4 with `$0.36` (day-to-day price drift). Claude was generating `qty = 0.01` for BTC, and the quoted price was `~$35.20`, so `0.01 × $35.20 = $0.35` — below the $1 floor.

## Root Cause

`backend/app/technical_analysis.py` uses `alpaca-py`'s `StockHistoricalDataClient` exclusively for all price data:

```python
_data_client: StockHistoricalDataClient | None = None

def _get_data_client() -> StockHistoricalDataClient:
    ...
    _data_client = StockHistoricalDataClient(...)
    return _data_client
```

This client covers only equity instruments. When the executor called `get_quote("BTC")`, Alpaca resolved it against the equities universe and returned data for an unrelated publicly-traded company with the ticker "BTC" on NYSE/AMEX — price ~$35.20. Real Bitcoin was trading at ~$104,000.

The prompt layer in `claude_brain.py` suggested BTC and ETH as valid tickers for two goals:

```python
# maximize_returns
"Focus on: AAPL, NVDA, MSFT, TSLA, GOOGL, AMZN, META, QQQ, XLK, BTC, ETH. "

# swing_trading
"Focus on: AAPL, MSFT, NVDA, TSLA, GOOGL, AMD, QQQ, BTC, ETH. "
```

Claude generated BTC buy orders. The stock client returned a plausible-looking but wrong price. The $1 guardrail blocked it. No exception was raised anywhere in the chain.

**The failure was a silent wrong-answer, not a crash.** The Alpaca client didn't error — it found an equities instrument named "BTC" and returned its price. This made the problem invisible to logs and tests.

## Fix

Removed BTC and ETH from both `GOAL_PROMPTS` entries in `backend/app/claude_brain.py`:

```python
# maximize_returns — before:
"Focus on: AAPL, NVDA, MSFT, TSLA, GOOGL, AMZN, META, QQQ, XLK, BTC, ETH. "
# after:
"Focus on: AAPL, NVDA, MSFT, TSLA, GOOGL, AMZN, META, QQQ, XLK. "

# swing_trading — before:
"Focus on: AAPL, MSFT, NVDA, TSLA, GOOGL, AMD, QQQ, BTC, ETH. "
# after:
"Focus on: AAPL, MSFT, NVDA, TSLA, GOOGL, AMD, QQQ. "
```

## What Proper Crypto Support Would Require

Adding crypto is non-trivial — it is not just a ticker list change:

1. **Separate data client:** `alpaca-py` provides `CryptoHistoricalDataClient` for crypto OHLCV. `technical_analysis.py` would need to route by asset class. Alpaca uses pair notation (`BTC/USD`) not bare symbols for crypto.

2. **Order routing:** Crypto orders require `TimeInForce.GTC` (or `IOC`) — `DAY` orders are invalid for crypto on Alpaca. The executor's order construction would need asset-class branching.

3. **24/7 market hours:** The scheduler and market-open guards assume NYSE hours. Crypto never closes; those checks would need conditional bypass for crypto positions.

4. **Symbol format:** The executor, guardrails, position tracking, and logging all key on symbol strings. Alpaca crypto uses `BTC/USD` — mixing bare `BTC` and pair-format symbols would silently break position lookups.

Until those four points are addressed end-to-end, BTC and ETH should remain out of the prompt lists.

## Related Documentation

- [`integration-issues/zero-qty-trades-pollute-audit-log.md`](../integration-issues/zero-qty-trades-pollute-audit-log.md) — Same downstream symptom: bad upstream data triggers the $1 minimum guardrail. That case: price = 0 from a failed lookup; this case: price = $35 from the wrong client.
- [`database-issues/sqlalchemy-decimal-float-sqlite-postgres-mismatch.md`](../database-issues/sqlalchemy-decimal-float-sqlite-postgres-mismatch.md) — Same class of bug: wrong interface for the instrument/environment returns a plausible-looking value that is silently wrong. No error thrown; corrupt downstream logic.

## Prevention

### Rule: Tickers in Prompts Must Match the Data Client That Will Price Them

This must be enforced structurally, not by convention. Specific rules:

**Rule 1 — No raw ticker strings in `GOAL_PROMPTS`.** Reference a typed constant or list. If you can't import and reference it, it doesn't belong in the prompt.

**Rule 2 — Crypto tickers use Alpaca pair format only.** `BTC/USD`, not `BTC`. The `/USD` suffix makes misrouting to the stock client a format error, not a silent mismatch.

**Rule 3 — `get_quote()` must become asset-class-aware.** Refactor `get_quote(ticker)` → `get_quote(ticker, asset_class)` and route to the correct client. Unknown tickers should raise, not fall through to the stock client.

### Monitoring: Catch This Sooner

**Signal 1 — Same ticker blocked for the same reason across multiple cycles.** A legitimate ticker gets blocked occasionally; the same ticker blocked every single cycle is a data or configuration failure. Query:

```sql
SELECT ticker, guardrail_block_reason, COUNT(*) AS count
FROM trades
WHERE executed = false AND action = 'buy'
  AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY ticker, guardrail_block_reason
HAVING COUNT(*) > 3
ORDER BY count DESC;
```

**Signal 2 — Abnormally low price on a buy attempt.** Add `quoted_price` to the block reason string. A query for `quoted_price < 1.00` on any non-penny ticker would have surfaced `BTC @ $35.20` immediately.

**Signal 3 — Claude mentions a ticker repeatedly but it never executes.** Cross-reference `claude_reasoning` text with `executed = true` trades over the last 30 cycles. A ticker that appears in reasoning but never executes is a systematic block worth investigating.

### Lightweight Regression Test

```python
# tests/test_goal_prompts.py
import re
from app.claude_brain import GOAL_PROMPTS

BARE_CRYPTO_SYMBOLS = {"BTC", "ETH", "SOL", "ADA", "DOGE"}

def test_no_bare_crypto_in_goal_prompts():
    """Bare crypto symbols must not appear in GOAL_PROMPTS — use BTC/USD format or omit."""
    for goal_key, prompt_text in GOAL_PROMPTS.items():
        for symbol in BARE_CRYPTO_SYMBOLS:
            if re.search(rf'\b{symbol}\b(?!/)', prompt_text):
                raise AssertionError(
                    f"Bare crypto symbol '{symbol}' in goal '{goal_key}'. "
                    f"Use '{symbol}/USD' (Alpaca pair format) or remove it entirely "
                    f"until CryptoHistoricalDataClient is integrated."
                )
```

This test would have caught the original bug immediately when BTC/ETH were first added to the prompts.
