"""Backtest simulation engine — lightweight day-by-day replay."""

import json
import logging
from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics import compute_metrics
from app.technical_analysis import _compute_indicators
from app.backtest.data import fetch_and_cache_bars, load_bars
from app.backtest.models import BacktestConfig, BacktestResult
from app.backtest.strategies import (
    STRATEGY_REGISTRY,
    PositionInfo,
    SimulationState,
)

logger = logging.getLogger(__name__)


async def run_backtest(config: BacktestConfig, db: Session) -> BacktestResult:
    """Execute a full backtest simulation.

    1. Fetch/cache OHLCV data
    2. Replay bars day-by-day through strategy
    3. Compute metrics from equity curve
    4. Return populated BacktestResult
    """
    result = (
        db.query(BacktestResult)
        .filter(BacktestResult.config_id == config.id)
        .first()
    )
    if not result:
        result = BacktestResult(config_id=config.id)
        db.add(result)
        db.flush()

    result.status = "running"
    result.started_at = datetime.now(timezone.utc)
    db.commit()

    try:
        tickers = config.get_tickers()
        params = config.get_params()

        # 1. Ensure we have cached OHLCV data
        await fetch_and_cache_bars(tickers, config.start_date, config.end_date, db)

        # 2. Load bars into DataFrames
        all_bars = load_bars(tickers, config.start_date, config.end_date, db)
        if not all_bars:
            raise ValueError("No OHLCV data available for the specified tickers and date range")

        # 3. Get strategy
        strategy_cls = STRATEGY_REGISTRY.get(config.strategy)
        if not strategy_cls:
            raise ValueError(f"Unknown strategy: {config.strategy}")
        strategy = strategy_cls()

        # 4. Collect all unique trading days across tickers
        all_dates: set[date] = set()
        for df in all_bars.values():
            all_dates.update(d.date() if hasattr(d, "date") else d for d in df.index)
        trading_days = sorted(all_dates)

        if not trading_days:
            raise ValueError("No trading days in the specified range")

        # 5. Simulate
        state = SimulationState(cash=config.initial_capital)

        for current_date in trading_days:
            # LOOKAHEAD PREVENTION: slice bars to current_date only
            bars_so_far = {}
            for ticker, df in all_bars.items():
                mask = df.index <= pd.Timestamp(current_date)
                sliced = df[mask]
                if not sliced.empty:
                    bars_so_far[ticker] = sliced

            if not bars_so_far:
                continue

            # Compute indicators on truncated data
            indicators = {}
            for ticker, df in bars_so_far.items():
                if len(df) >= 14:
                    ind = _compute_indicators(df)
                    if ind:
                        indicators[ticker] = ind

            # Get strategy signals
            signals = strategy.decide(
                current_date=current_date,
                indicators=indicators,
                state=state,
                bars=bars_so_far,
                params=params,
            )

            # Execute signals
            for signal in signals:
                ticker = signal.ticker
                if ticker not in bars_so_far:
                    continue
                price = float(bars_so_far[ticker].iloc[-1]["close"])

                if signal.action == "buy" and ticker not in state.positions:
                    # Position sizing: equal weight capped by config
                    equity = _compute_equity(state, bars_so_far, current_date)
                    max_alloc = equity * config.max_position_pct
                    alloc = min(max_alloc, state.cash * 0.95)  # Keep 5% cash buffer
                    if alloc < price or len(state.positions) >= config.max_positions:
                        continue
                    qty = int(alloc / price)
                    cost = qty * price
                    state.cash -= cost
                    state.positions[ticker] = PositionInfo(quantity=qty, avg_price=price)
                    state.trades.append({
                        "date": str(current_date),
                        "ticker": ticker,
                        "action": "buy",
                        "quantity": qty,
                        "price": round(price, 2),
                        "reason": signal.reason,
                        "confidence": round(signal.confidence, 2),
                    })

                elif signal.action == "sell" and ticker in state.positions:
                    pos = state.positions.pop(ticker)
                    proceeds = pos.quantity * price
                    state.cash += proceeds
                    state.trades.append({
                        "date": str(current_date),
                        "ticker": ticker,
                        "action": "sell",
                        "quantity": pos.quantity,
                        "price": round(price, 2),
                        "reason": signal.reason,
                        "confidence": round(signal.confidence, 2),
                    })

            # Stop-loss check
            for ticker in list(state.positions.keys()):
                if ticker not in bars_so_far:
                    continue
                price = float(bars_so_far[ticker].iloc[-1]["close"])
                pos = state.positions[ticker]
                loss_pct = (price - pos.avg_price) / pos.avg_price
                if loss_pct <= -config.stop_loss_pct:
                    proceeds = pos.quantity * price
                    state.cash += proceeds
                    state.trades.append({
                        "date": str(current_date),
                        "ticker": ticker,
                        "action": "sell",
                        "quantity": pos.quantity,
                        "price": round(price, 2),
                        "reason": f"Stop-loss triggered at {loss_pct*100:.1f}%",
                        "confidence": 1.0,
                    })
                    del state.positions[ticker]

            # Mark to market
            equity = _compute_equity(state, bars_so_far, current_date)
            state.equity_curve.append({
                "date": str(current_date),
                "equity": round(equity, 2),
            })

        # 6. Compute metrics
        equities = [pt["equity"] for pt in state.equity_curve]
        metrics = compute_metrics(equities)

        result.status = "completed"
        result.completed_at = datetime.now(timezone.utc)
        result.total_return_pct = metrics.total_return_pct
        result.sharpe_ratio = metrics.sharpe_ratio
        result.sortino_ratio = metrics.sortino_ratio
        result.max_drawdown_pct = metrics.max_drawdown_pct
        result.win_rate_pct = metrics.win_rate_pct
        result.profit_factor = metrics.profit_factor
        result.total_trades = len(state.trades)
        result.equity_curve = json.dumps(state.equity_curve)
        result.trades_log = json.dumps(state.trades)
        db.commit()

        logger.info(
            "Backtest complete: %s — return=%.1f%%, sharpe=%s, trades=%d",
            config.name, metrics.total_return_pct,
            metrics.sharpe_ratio, len(state.trades),
        )

    except Exception as e:
        result.status = "failed"
        result.error_message = str(e)
        result.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error("Backtest failed: %s", e)

    return result


def _compute_equity(
    state: SimulationState,
    bars: dict[str, pd.DataFrame],
    current_date: date,
) -> float:
    """Compute total equity = cash + sum(position values at current close)."""
    total = state.cash
    for ticker, pos in state.positions.items():
        if ticker in bars and not bars[ticker].empty:
            price = float(bars[ticker].iloc[-1]["close"])
            total += pos.quantity * price
    return total
