"""Per-plan trading executor with virtual cash tracking."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app import claude_brain, market_data, notifier
from app.guardrails import apply_risk_preset
from app.decision_coercion import coerce_bad_price_to_hold, coerce_zero_qty_to_hold
from app.pipeline_types import CycleResult
from app.earnings.client import days_until_earnings, format_earnings_csv
from app.circuit_breaker import check_circuit_breakers, RED
from app.technical_analysis import get_indicators, format_indicators_csv
from app.sector_rotation import get_sector_signals, format_sector_csv
from app.brokers.alpaca import AlpacaBroker
from app.models import Trade
from app.plans.models import Portfolio
from app.plans.constraints import check_trading_constraints, update_touch_history

logger = logging.getLogger(__name__)

broker = AlpacaBroker()

# 061-fix: Per-plan asyncio locks prevent concurrent runs of the same plan
# from double-spending virtual cash (e.g., scheduler + manual /run collision).
# Broker-level order serialization is handled by `order_lock` in alpaca.py (069-fix).
_plan_locks: dict[int, asyncio.Lock] = {}


def _get_plan_lock(plan_id: int) -> asyncio.Lock:
    """Return the asyncio lock for a given plan_id, creating it on first use."""
    return _plan_locks.setdefault(plan_id, asyncio.Lock())


def compute_virtual_positions(db: Session, plan_id: int) -> dict[str, float]:
    """Compute net shares per ticker from executed trades for a portfolio."""
    rows = (
        db.query(
            Trade.ticker,
            func.sum(
                case(
                    (Trade.action == "buy", Trade.quantity),
                    (Trade.action == "sell", -Trade.quantity),
                    else_=0,
                )
            ).label("net_qty"),
        )
        .filter(Trade.portfolio_id == plan_id, Trade.executed.is_(True))
        .group_by(Trade.ticker)
        .all()
    )
    return {row.ticker: float(row.net_qty) for row in rows if row.net_qty > 0}


def _plan_to_guardrails_config(plan: Portfolio) -> dict:
    """Convert a Portfolio to a guardrails config dict for Claude.

    071-fix: Convert Decimal fields to float at the boundary — guardrails
    and Claude prompt use float arithmetic throughout.
    """
    budget = float(plan.budget)
    config = apply_risk_preset(plan.risk_profile, budget)
    config["trading_goal"] = plan.trading_goal
    config["trading_frequency"] = plan.trading_frequency
    config["max_total_invested"] = budget
    config["max_single_trade_size"] = min(config["max_single_trade_size"], budget * 0.5)
    config["kill_switch"] = False
    if plan.target_amount:
        config["target_amount"] = float(plan.target_amount)
    if plan.target_date:
        config["target_date"] = plan.target_date
    return config


def _live_state_for_strategy(plan: Portfolio, db: Session):
    """Build a SimulationState from live virtual positions for strategy.decide()."""
    from app.backtest.strategies import PositionInfo, SimulationState

    virtual_positions = compute_virtual_positions(db, plan.id)
    positions_info = {
        ticker: PositionInfo(quantity=max(1, int(qty)), avg_price=0.0)
        for ticker, qty in virtual_positions.items()
    }
    return SimulationState(cash=float(plan.virtual_cash), positions=positions_info)


async def _get_strategy_decisions(
    plan: Portfolio,
    db: Session,
    price_map: dict[str, float],
) -> list[dict]:
    """Derive trade decisions from a deterministic strategy (rules_decide mode).

    Fetches recent OHLCV bars, runs the registered strategy, and translates
    StrategySignal objects into the same TradeDecision dict format the Claude
    path produces — so the rest of the executor loop is mode-agnostic.

    # TODO: move fetch_and_cache_bars / load_bars out of app.backtest to
    # app.market_data so they can be shared without violating feature isolation.
    """
    from datetime import date as _date, timedelta
    from app.strategies import STRATEGY_REGISTRY
    from app.backtest.data import fetch_and_cache_bars, load_bars
    from app.backtest.strategies import PositionInfo, SimulationState
    from app.technical_analysis import _compute_indicators
    from app.claude_brain import GOAL_WATCHLIST

    strategy_cls = STRATEGY_REGISTRY.get(plan.strategy_id or "")
    if not strategy_cls:
        logger.warning("Plan %d: unknown strategy '%s' — holding", plan.id, plan.strategy_id)
        return [{"action": "hold", "ticker": "", "quantity": 0,
                 "reasoning": f"Unknown strategy: {plan.strategy_id}", "confidence": 0.0}]

    strategy = strategy_cls()
    params = plan.strategy_params or {}

    # Build ticker universe: owned positions + goal watchlist + strategy-specific tickers
    virtual_positions = compute_virtual_positions(db, plan.id)
    tickers: set[str] = set(virtual_positions.keys())
    tickers.update(GOAL_WATCHLIST.get(plan.trading_goal, []))
    if isinstance(params.get("tickers"), list):
        tickers.update(params["tickers"])
    # DualMomentum always needs SPY, VEU, BIL for its momentum comparison
    if plan.strategy_id == "dual_momentum":
        tickers.update(["SPY", "VEU", "BIL"])
    tickers.discard("")
    tickers_list = sorted(tickers)

    if not tickers_list:
        return [{"action": "hold", "ticker": "", "quantity": 0,
                 "reasoning": "No tickers to evaluate", "confidence": 0.0}]

    # Fetch ~14 months of daily bars (DualMomentum needs 12-month lookback + warm-up)
    today = _date.today()
    start = today - timedelta(days=420)
    await fetch_and_cache_bars(tickers_list, start, today, db)
    all_bars = load_bars(tickers_list, start, today, db)

    if not all_bars:
        return [{"action": "hold", "ticker": "", "quantity": 0,
                 "reasoning": "No OHLCV data available for strategy", "confidence": 0.0}]

    # Compute indicators on the full bar history
    indicators: dict = {}
    for ticker, df in all_bars.items():
        if len(df) >= 14:
            ind = _compute_indicators(df)
            if ind:
                indicators[ticker] = ind

    # Build live state from virtual positions
    state = _live_state_for_strategy(plan, db)

    signals = strategy.decide(
        current_date=today,
        indicators=indicators,
        state=state,
        bars=all_bars,
        params=params,
    )

    if not signals:
        return [{"action": "hold", "ticker": "", "quantity": 0,
                 "reasoning": "Strategy returned no signals for this cycle", "confidence": 0.0}]

    # Translate StrategySignal → TradeDecision dict format + position sizing
    budget = float(plan.budget)
    max_position_pct = float(plan.kelly_fraction)
    decisions: list[dict] = []

    for signal in signals:
        if signal.action == "hold":
            decisions.append({
                "action": "hold",
                "ticker": signal.ticker or "",
                "quantity": 0,
                "reasoning": signal.reason,
                "confidence": signal.confidence,
            })

        elif signal.action == "buy":
            price = price_map.get(signal.ticker, 0.0)
            if price <= 0:
                logger.info("Plan %d: no live price for %s — skipping buy signal", plan.id, signal.ticker)
                continue
            # Size proportional to confidence, capped at max_position_pct of budget
            alloc = min(budget * max_position_pct * signal.confidence, float(plan.virtual_cash) * 0.95)
            qty = round(alloc / price, 4) if alloc > 0 else 0.0
            if qty <= 0:
                continue
            decisions.append({
                "action": "buy",
                "ticker": signal.ticker,
                "quantity": qty,
                "reasoning": signal.reason,
                "confidence": signal.confidence,
            })

        elif signal.action == "sell":
            own_qty = virtual_positions.get(signal.ticker, 0.0)
            if own_qty <= 0:
                logger.info("Plan %d: sell signal for %s but not held — skipping", plan.id, signal.ticker)
                continue
            decisions.append({
                "action": "sell",
                "ticker": signal.ticker,
                "quantity": own_qty,
                "reasoning": signal.reason,
                "confidence": signal.confidence,
            })

    return decisions or [{"action": "hold", "ticker": "", "quantity": 0,
                          "reasoning": "Strategy produced no actionable signals", "confidence": 0.0}]


async def run_plan_cycle(
    db: Session,
    plan: Portfolio,
    positions: list,
    balance: dict,
    quotes: list,
    news: list,
    technicals_csv: str,
    sector_csv: str,
    earnings_csv: str,
) -> list[CycleResult]:
    """Execute a trading cycle for a single portfolio using shared market data.

    087-fix: Inlined the per-plan lock (was a separate wrapper/_locked split).
    061-fix: Per-plan lock prevents concurrent runs from double-spending.
    063-fix: Commits each trade individually right after Alpaca order.
    """
    async with _get_plan_lock(plan.id):
        # Re-read plan inside the lock to get the latest virtual_cash
        db.refresh(plan)
        return await _execute_plan_cycle(
            db, plan, positions, balance,
            quotes, news, technicals_csv, sector_csv, earnings_csv,
        )


async def _execute_plan_cycle(
    db: Session,
    plan: Portfolio,
    positions: list,
    balance: dict,
    quotes: list,
    news: list,
    technicals_csv: str,
    sector_csv: str,
    earnings_csv: str,
) -> list[CycleResult]:

    # Build plan-specific context
    virtual_positions = compute_virtual_positions(db, plan.id)
    plan_config = _plan_to_guardrails_config(plan)

    # 098-fix: Build price lookup dict once instead of O(T) linear scans per ticker
    price_map = {q["ticker"]: q["price"] for q in quotes}

    # Convert virtual positions to the format Claude expects
    plan_positions = [
        {
            "instrument": {"symbol": ticker, "asset_type": "stock"},
            "quantity": qty,
            "market_value": qty * price_map.get(ticker, 0),
            "cost_basis": 0,
            "unrealized_pnl": 0,
            "unrealized_pnl_pct": 0,
        }
        for ticker, qty in virtual_positions.items()
    ]

    # Compute plan-level usage so Claude can size proposals to fit. Without
    # this Claude saw `cash_available=$0.21` only as a portfolio-line
    # mention and kept proposing $99 buys — the explicit HEADROOM block in
    # the prompt makes the binding constraint impossible to miss.
    plan_total_invested = float(plan.budget) - float(plan.virtual_cash)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    plan_orders_today = await asyncio.to_thread(
        lambda: db.query(Trade)
        .filter(
            Trade.portfolio_id == plan.id,
            Trade.timestamp >= today_start,
            Trade.executed.is_(True),
        )
        .count()
    )

    # === Decision generation — branched by portfolio.decision_mode ===
    if plan.decision_mode == "rules_decide":
        decisions = await _get_strategy_decisions(plan, db, price_map)
    elif plan.decision_mode == "rules_with_claude_oversight":
        strategy_decisions = await _get_strategy_decisions(plan, db, price_map)
        oversight_context = {
            "cash_available": float(plan.virtual_cash),
            "positions": plan_positions,
            "quotes": quotes,
            "news": news,
            "technicals_csv": technicals_csv,
            "earnings_csv": earnings_csv,
            "sector_csv": sector_csv,
            "trading_goal": plan.trading_goal,
            "risk_profile": plan.risk_profile,
        }
        decisions = []
        for sd in strategy_decisions:
            review = await claude_brain.review_trade_decision(sd, oversight_context, plan)
            decision = sd.copy()
            decision["_rules_recommendation"] = {k: v for k, v in sd.items() if not k.startswith("_")}
            if not review.get("confirmed", True) and review.get("override_decision"):
                override = review["override_decision"]
                for key in ("action", "ticker", "quantity", "confidence"):
                    if key in override:
                        decision[key] = override[key]
                decision["reasoning"] = (
                    f"[Strategy: {sd.get('reasoning', '')}] "
                    f"[Claude override: {review.get('reasoning', '')}]"
                )
            else:
                decision["reasoning"] = (
                    f"{sd.get('reasoning', '')} "
                    f"[Claude confirmed: {review.get('reasoning', '')}]"
                ).strip()
            decisions.append(decision)
    else:
        # "claude_decides" — existing behavior, unchanged
        decisions = await claude_brain.get_trade_decision(
            positions=plan_positions,
            cash_available=float(plan.virtual_cash),
            market_data=quotes,
            news=news,
            guardrails_config=plan_config,
            technicals_csv=technicals_csv,
            sector_csv=sector_csv,
            earnings_csv=earnings_csv,
            total_invested=plan_total_invested,
            orders_used_today=plan_orders_today,
        )
    # === End decision generation ===

    results: list[CycleResult] = []
    # 071-fix: Convert Decimal to float — executor uses float arithmetic throughout
    remaining_cash = float(plan.virtual_cash)

    plan_log_prefix = f"Plan {plan.id}: "

    for decision in decisions:
        logger.info(
            "Plan %d: Claude → action=%s ticker=%s qty=%s conf=%.0f%% | %s",
            plan.id,
            decision.get("action"),
            decision.get("ticker"),
            decision.get("quantity"),
            (decision.get("confidence") or 0) * 100,
            (decision.get("reasoning") or "")[:120],
        )
        # Coerce degenerate decisions to holds BEFORE validation —
        # see app/decision_coercion.py for rationale.
        coerce_zero_qty_to_hold(decision, log_prefix=plan_log_prefix)

        price = None
        if decision["ticker"] and decision["action"] != "hold":
            cached_price = price_map.get(decision["ticker"])
            if cached_price is not None:
                price = cached_price
            else:
                quote = await market_data.get_quote(decision["ticker"])
                price = quote["price"]
            decision["price"] = price

            if coerce_bad_price_to_hold(decision, price, log_prefix=plan_log_prefix):
                price = None

            # Position sizing
            if decision["action"] == "buy" and price:
                from app.position_sizing import kelly_position_size
                ed = days_until_earnings(db, decision["ticker"])
                max_size = kelly_position_size(
                    confidence=decision.get("confidence", 0.5),
                    portfolio_value=float(plan.budget),
                    db=db,
                    earnings_days=ed,
                )
                if max_size > 0:
                    max_qty = int(max_size / price)
                    if max_qty > 0 and decision["quantity"] > max_qty:
                        decision["quantity"] = max_qty

            # SECURITY: Sell validation — prevent cross-plan position theft
            if decision["action"] == "sell":
                plan_qty = virtual_positions.get(decision["ticker"], 0)
                if decision["quantity"] > plan_qty:
                    logger.warning(
                        "Plan %d: sell blocked — owns %.2f of %s, tried to sell %d",
                        plan.id, plan_qty, decision["ticker"], decision["quantity"],
                    )
                    decision["quantity"] = 0
                    decision["action"] = "hold"
                    decision["reasoning"] = f"Sell blocked: plan only owns {plan_qty:.2f} shares"

        # 072-fix: Trading constraints — cooldown, frequency caps, no-repeat action
        decision_ts = datetime.now(timezone.utc)
        if decision["action"] != "hold":
            allowed, constraint_reason = await check_trading_constraints(
                db, plan, decision, decision_ts
            )
            if not allowed:
                logger.info(
                    "Plan %d: constraint blocked %s: %s",
                    plan.id, decision["ticker"], constraint_reason,
                )
                decision["action"] = "hold"
                decision["reasoning"] = constraint_reason
                decision["quantity"] = 0

        # 072-fix: Auto-size buy orders to fractional shares if cash is
        # insufficient. Update the reasoning field so the audit trail reflects
        # the actual quantity (previously Claude's "buy 1 share" would be
        # silently logged as "buy 0.25 share" with unchanged reasoning).
        if decision["action"] == "buy" and price and price > 0:
            trade_value = price * decision.get("quantity", 0)
            # Keep 5% buffer for slippage; minimum $1 order
            max_affordable = max(remaining_cash * 0.95, 0)
            if trade_value > max_affordable and max_affordable >= 1.0:
                new_qty = round(max_affordable / price, 4)
                if new_qty >= 0.0001:
                    original_qty = decision["quantity"]
                    logger.info(
                        "Plan %d: reducing %s qty from %s to %s (cash $%.2f)",
                        plan.id, decision["ticker"], original_qty, new_qty, remaining_cash,
                    )
                    decision["quantity"] = new_qty
                    decision["reasoning"] = (
                        f"{decision.get('reasoning', '')} "
                        f"[Auto-resized from {original_qty} to {new_qty} shares "
                        f"to fit plan cash of ${remaining_cash:.2f}]"
                    ).strip()

        # Guardrail check with plan-scoped values
        trade_value = (price or 0) * decision.get("quantity", 0)
        invested = float(plan.budget) - remaining_cash
        passed = True
        block_reason = None

        if decision["action"] == "buy":
            if trade_value > remaining_cash:
                passed = False
                block_reason = f"Insufficient plan cash: ${remaining_cash:.2f} < ${trade_value:.2f}"
            elif trade_value < 1.0:
                passed = False
                block_reason = f"Trade value $${trade_value:.2f} below $1 minimum"
            elif invested + trade_value > float(plan.budget):
                passed = False
                block_reason = f"Would exceed plan budget of ${float(plan.budget):.0f}"
            elif decision.get("confidence", 0) < plan_config.get("min_confidence", 0.6):
                passed = False
                block_reason = f"Confidence {decision.get('confidence', 0):.0%} below minimum {plan_config.get('min_confidence', 0.6):.0%}"

        # 069-fix: Broker-level order_lock handles concurrent order protection;
        # no need for a plan-executor-level lock here.
        executed = False
        alpaca_order_id: str | None = None
        cash_before = remaining_cash
        if passed and decision["action"] in ("buy", "sell") and decision.get("quantity", 0) > 0:
            try:
                # 080-fix: Capture broker return for reconciliation tracking
                order_result = await broker.place_order(
                    account_id="default",
                    ticker=decision["ticker"],
                    action=decision["action"],
                    quantity=decision["quantity"],
                )
                alpaca_order_id = order_result.get("order_id") if order_result else None
                executed = True
                if decision["action"] == "buy":
                    remaining_cash -= trade_value
                else:
                    remaining_cash += trade_value
                logger.info(
                    "Plan %d: executed %s %s shares of %s (Alpaca order %s)",
                    plan.id, decision["action"],
                    decision["quantity"], decision["ticker"], alpaca_order_id,
                )
            except Exception as e:
                logger.error("Plan %d: order failed: %s", plan.id, e)
                block_reason = f"Execution error: {e}"
                passed = False

        # 063-fix: Log trade + update plan cash + commit atomically per decision,
        # immediately after the Alpaca order. This closes the cash-duplication
        # window where a later commit failure would leave a real order unlogged.
        # Pop before Trade creation — _rules_recommendation is an audit artifact,
        # not a field on the decision dict that downstream code should see.
        rules_rec = decision.pop("_rules_recommendation", None)
        plan_trade = Trade(
            portfolio_id=plan.id,
            ticker=decision.get("ticker", ""),
            action=decision["action"],
            quantity=decision.get("quantity", 0),
            price=price,
            claude_reasoning=decision.get("reasoning"),
            confidence=decision.get("confidence"),
            guardrail_passed=passed,
            guardrail_block_reason=block_reason,
            executed=executed,
            alpaca_order_id=alpaca_order_id,
            virtual_cash_before=cash_before,
            virtual_cash_after=remaining_cash,
            rules_recommendation=rules_rec,
        )
        db.add(plan_trade)
        if executed:
            plan.virtual_cash = remaining_cash
        try:
            db.commit()
            db.refresh(plan_trade)
            # 072-fix: Update touch history for constraint checking on next cycle
            if executed and plan_trade.action.lower() in ("buy", "sell"):
                await update_touch_history(db, plan, plan_trade, decision_ts)
        except Exception as e:
            db.rollback()
            # 080-fix: Include Alpaca order ID in the reconciliation log
            # so operators can match the executed order to the unwritten state.
            logger.exception(
                "Plan %d: DB commit failed — RECONCILIATION NEEDED. "
                "Alpaca order_id=%s ticker=%s action=%s qty=%s executed=%s. Error: %s",
                plan.id, alpaca_order_id, decision.get("ticker"), decision["action"],
                decision.get("quantity"), executed, e,
            )
            # Re-raise to stop the cycle; other plans continue in run_all_plans
            raise

        result: CycleResult = {
            "trade_id": plan_trade.id,
            "action": decision["action"],
            "ticker": decision.get("ticker", ""),
            "quantity": decision.get("quantity", 0),
            "price": price,
            "executed": executed,
            "guardrail_passed": passed,
            "guardrail_block_reason": block_reason,
            "reasoning": decision.get("reasoning", ""),
            "confidence": decision.get("confidence", 0),
        }
        results.append(result)

    return results


async def fetch_market_data(
    db: Session,
    plan_ids: list[int],
    plans: list[Portfolio] | None = None,
) -> tuple[list, dict, list, list, str, str, str]:
    """Fetch shared market data for one or more plans.

    089-fix: Extracted from run_all_plans so run_plan route can reuse it.
    068-fix: Unions Alpaca account tickers with per-plan virtual position tickers.
    093-fix: Also seeds watchlist tickers from each plan's trading goal so
             empty portfolios get price quotes to evaluate before placing first buy.

    Returns (positions, balance, quotes, news, technicals_csv, sector_csv, earnings_csv).
    """
    from app.claude_brain import GOAL_WATCHLIST

    positions, balance = await asyncio.gather(
        broker.get_positions("default"),
        broker.get_account_balance("default"),
    )

    # Union account tickers + per-plan virtual positions + goal watchlists.
    all_tickers = {p.get("instrument", {}).get("symbol", "") for p in positions}
    for pid in plan_ids:
        all_tickers.update(compute_virtual_positions(db, pid).keys())
    if plans:
        for plan in plans:
            all_tickers.update(GOAL_WATCHLIST.get(plan.trading_goal, []))
            # Per-portfolio universe override (claude_decides path). This is also
            # the slot a daily screener writes its top candidates into. Previously
            # strategy_params["tickers"] was only honored by the rules-strategy
            # path — so Claude-mode portfolios silently ignored it.
            extra = (plan.strategy_params or {}).get("tickers")
            if isinstance(extra, list):
                all_tickers.update(t for t in extra if isinstance(t, str) and t)
    all_tickers.discard("")
    held_tickers = sorted(all_tickers)

    quotes_task = market_data.get_quotes(held_tickers) if held_tickers else asyncio.sleep(0, result=[])
    news_task = market_data.get_news(held_tickers if held_tickers else None)
    indicators_task = get_indicators(held_tickers) if held_tickers else asyncio.sleep(0, result={})
    sector_task = get_sector_signals()
    quotes, news, indicators, sector_signals = await asyncio.gather(
        quotes_task, news_task, indicators_task, sector_task
    )

    # Patch any price=0 quotes with Alpaca close prices from indicators.
    # Alpha Vantage free tier (5 req/min) gets rate-limited when fetching
    # many tickers simultaneously, returning price=0 and triggering coerce.
    if indicators:
        covered = {q["ticker"] for q in quotes}
        quotes = [
            {**q, "price": indicators[q["ticker"]]["price"]}
            if q.get("price", 0) <= 0 and q["ticker"] in indicators
            else q
            for q in quotes
        ]
        for ticker, data in indicators.items():
            if ticker not in covered and data.get("price", 0) > 0:
                quotes.append({"ticker": ticker, "price": data["price"], "change_pct": 0.0, "volume": 0})

    technicals_csv = format_indicators_csv(indicators)
    sector_csv = format_sector_csv(sector_signals)
    earnings_csv = format_earnings_csv(db, held_tickers) if held_tickers else ""

    return positions, balance, quotes, news, technicals_csv, sector_csv, earnings_csv


async def run_all_plans(db: Session) -> dict[int, list[CycleResult]]:
    """Run trading cycles for all active portfolios with shared market data.

    Portfolio-only model: there is no global kill switch. Each portfolio's
    is_active flag serves as its own kill switch — set is_active=False to
    halt that portfolio. The broker-wide circuit breaker still triggers on
    account-level drawdown and, when RED, deactivates every active portfolio
    in one shot (faster than per-portfolio toggles in a panic).
    """

    # 1. Shared data fetch (once for all portfolios)
    positions_raw, balance = await asyncio.gather(
        broker.get_positions("default"),
        broker.get_account_balance("default"),
    )

    # 2. Account-wide circuit breaker — uses default thresholds (5% / 10%).
    # Per-portfolio thresholds (Portfolio.circuit_breaker_*) are honored
    # inside each portfolio's own validation.
    cb_level, cb_reason = check_circuit_breakers(
        db=db, portfolio_value=balance["total_value"], config={},
    )
    if cb_level == RED:
        logger.warning("Circuit breaker RED: %s — deactivating all portfolios", cb_reason)
        for p in db.query(Portfolio).filter(Portfolio.is_active.is_(True)).all():
            p.is_active = False
        db.commit()
        return {}

    # 3. Get active portfolios so we can include their tickers in market data
    active_plans = db.query(Portfolio).filter(Portfolio.is_active.is_(True)).all()
    if not active_plans:
        logger.info("No active plans")
        return {}

    # 089-fix: Use shared fetch_market_data for consistent ticker union
    # 093-fix: Pass plans so watchlist tickers are seeded for empty portfolios
    positions, balance, quotes, news, technicals_csv, sector_csv, earnings_csv = (
        await fetch_market_data(db, [p.id for p in active_plans], plans=active_plans)
    )

    # 4. Run each plan's cycle (Claude call happens inside run_plan_cycle).
    # 064-fix: removed wasted asyncio.gather of Claude calls whose results
    # were discarded; run_plan_cycle makes its own Claude call.
    all_results: dict[int, list[CycleResult]] = {}
    for plan in active_plans:
        try:
            results = await run_plan_cycle(
                db, plan, positions, balance,
                quotes, news, technicals_csv, sector_csv, earnings_csv,
            )
            all_results[plan.id] = results
            for r in results:
                await notifier.notify_trade(r)
        except Exception as e:
            logger.exception("Plan %d cycle failed: %s", plan.id, e)
            # Continue with other plans — one plan's failure shouldn't block others

    return all_results
