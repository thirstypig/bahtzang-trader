---
id: DOC-027
type: guide
status: active
phase: null
owner: james
tags: [strategies]
links: []
updated: 2026-07-22
---

# Adding a New Strategy

Strategies live in `backend/app/strategies/` — a shared infrastructure package, not a feature module. Adding a new one is a 3-step process.

---

## Step 1 — Implement

Create `backend/app/strategies/<your_strategy>.py`. Subclass `BaseStrategy` from `app.strategies.base`:

```python
from app.strategies.base import BaseStrategy, StrategySignal

class YourStrategy(BaseStrategy):
    """One-line description of the strategy."""

    default_params = {
        "param_one": 10,
        "param_two": 0.5,
    }

    def generate_signals(
        self,
        tickers: list[str],
        price_data: dict[str, list[float]],
        params: dict,
    ) -> list[StrategySignal]:
        """Return a list of StrategySignal objects, one per ticker."""
        signals = []
        for ticker in tickers:
            prices = price_data.get(ticker, [])
            if not prices:
                continue
            # ... your logic ...
            signals.append(StrategySignal(
                ticker=ticker,
                action="buy",   # "buy" | "sell" | "hold"
                quantity=10,
                confidence=0.70,
                reasoning="Your signal rationale here",
            ))
        return signals
```

**`StrategySignal` fields:**
- `ticker` (str) — required
- `action` (str) — `"buy"`, `"sell"`, or `"hold"`
- `quantity` (float) — number of shares for buy/sell; 0 for hold
- `confidence` (float, 0–1) — passed to the guardrails min_confidence check
- `reasoning` (str) — stored in `claude_reasoning` and shown in the UI

**Price data:** `price_data` is a `dict[ticker → list[float]]` of recent closing prices, most recent last. The backtest engine and live executor both provide this in the same format.

---

## Step 2 — Register

Open `backend/app/strategies/registry.py` and add your strategy to `STRATEGY_REGISTRY`:

```python
from app.strategies.your_strategy import YourStrategy

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "sma_crossover": SMACrossover,
    "rsi_mean_reversion": RSIMeanReversion,
    "buy_and_hold": BuyAndHold,
    "dual_momentum": DualMomentum,
    "your_strategy": YourStrategy,   # ← add this
}
```

Also add the parameter schema to `get_strategy_info()` in `registry.py` so the frontend Decision Engine can render input fields for it:

```python
"your_strategy": {
    "name": "Your Strategy Name",
    "description": "One-line description shown in the UI",
    "params": [
        {"key": "param_one", "label": "Param One", "type": "int", "default": 10},
        {"key": "param_two", "label": "Param Two", "type": "number", "default": 0.5},
    ],
},
```

Param types: `"int"`, `"number"`, `"boolean"`, `"list"` (comma-separated tickers), `"string"`.

---

## Step 3 — Test and optionally backtest

**Unit tests:** Add `backend/tests/test_<your_strategy>_strategy.py`. Test `generate_signals()` directly with synthetic price data. See `test_dual_momentum_strategy.py` for the pattern.

**Backtest:** Run a backtest from `/backtest` in the UI, select your new strategy, and check the equity curve and per-trade log. The backtest engine uses the same `generate_signals()` method — no separate backtest implementation needed.

**Live trial:** Once satisfied, create a portfolio with `decision_mode = "rules_decide"` and `strategy_id = "your_strategy"`. This runs the strategy live without any Claude API calls.

---

## Current Strategies

| ID | Class | Summary |
|----|-------|---------|
| `sma_crossover` | `SMACrossover` | 50/200 SMA golden/death cross |
| `rsi_mean_reversion` | `RSIMeanReversion` | RSI 30/70 overbought/oversold |
| `buy_and_hold` | `BuyAndHold` | Equal-weight benchmark (buy day 1, hold) |
| `dual_momentum` | `DualMomentum` | Antonacci: SPY vs VEU monthly rotation, BIL when both negative |

---

## Notes

- **Isolation:** `app/strategies/` is shared infrastructure. Do not import it from inside a feature module — always import from `app.strategies`, not `app.backtest.strategies`.
- **No DB state:** Strategies are stateless — they receive price data and return signals. Any persistence (e.g., last signal date) belongs on the Portfolio model, not inside the strategy class.
- **Parameter coercion:** The executor coerces string parameters from the UI (`strategy_params`) to their declared types before passing them to `generate_signals()`. Declare types accurately in `get_strategy_info()`.
