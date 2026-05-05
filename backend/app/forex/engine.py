"""Bar-by-bar backtest engine for the swing-zone strategy.

State machine per symbol:
    zones (rebuilt each new ISO week from prior weekly history)
        ↓ price closes at/past midpoint
    armed
        ↓ next daily bar fires the matching reversal pattern
    pending_entry
        ↓ next daily bar opens
    open position (with bracket SL/TP and zone-break invalidation)

Order of intraday exit resolution (pessimistic):
    1. SL hit (bar low/high crosses SL)
    2. TP hit (bar high/low crosses TP)
    3. Zone-break on close (daily close past the zone's far edge)
    4. Carry
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from app.forex.data import fetch_daily_bars, resample_to_weekly
from app.forex.patterns import Candle, detect_bearish_reversal, detect_bullish_reversal
from app.forex.zones import Zone, build_zones


@dataclass
class Position:
    symbol: str
    direction: str  # "long" | "short"
    entry_date: date
    entry_price: float
    stop_loss: float
    take_profit: float
    units: float
    zone: Zone
    bars_open: int = 0


EARLY_EXIT_MODES = ("none", "progress", "time_band")


def _unrealized_r(pos: Position, price: float) -> float:
    """Unrealized P&L expressed in R units (=risk), where +1.0R = TP, -1.0R = SL."""
    if pos.direction == "long":
        r_dist = pos.entry_price - pos.stop_loss
        return (price - pos.entry_price) / r_dist if r_dist > 0 else 0.0
    r_dist = pos.stop_loss - pos.entry_price
    return (pos.entry_price - price) / r_dist if r_dist > 0 else 0.0


def _evaluate_early_exit(
    pos: Position,
    close_price: float,
    mode: str,
    min_bars: int,
    threshold_r: float,
) -> tuple[float | None, str | None]:
    """Discretionary close on today's bar's close. Evaluated only after the
    intraday SL/TP/zone-break checks find no exit.

    - "progress":  close if unrealized R is below `threshold_r` once `bars_open`
                   reaches `min_bars`. Cuts losers and meanderers, lets winners run.
    - "time_band": close if unrealized R is within ±`threshold_r` after `min_bars`.
                   Cuts only meanderers; preserves both committed losers and winners.
    """
    if mode == "none" or pos.bars_open < min_bars:
        return None, None
    r = _unrealized_r(pos, close_price)
    if mode == "progress" and r < threshold_r:
        return close_price, "early_exit_progress"
    if mode == "time_band" and -threshold_r <= r <= threshold_r:
        return close_price, "early_exit_band"
    return None, None


@dataclass
class SymbolState:
    zones: list[Zone] = field(default_factory=list)
    armed: set[int] = field(default_factory=set)
    pending_entry: tuple[Zone, str] | None = None
    position: Position | None = None
    last_rebuild_iso: tuple[int, int] | None = None


@dataclass
class BacktestOutput:
    final_equity: float
    total_return_pct: float
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    equity_curve: list[dict]
    trades_log: list[dict]


def quote_to_usd(quote_amount: float, symbol: str, current_price: float) -> float:
    """Convert P&L expressed in the pair's quote currency into USD.

    Convention: symbol = BASE+QUOTE (6 chars, e.g. EURUSD, USDJPY).
    USD-quoted pairs (xxxUSD): quote already in USD → identity.
    USD-base pairs (USDxxx): 1 unit of quote currency = 1/price USD.
    """
    sym = symbol.upper()
    if sym.endswith("USD"):
        return quote_amount
    if sym.startswith("USD") and current_price > 0:
        return quote_amount / current_price
    return quote_amount


def _evaluate_exit(pos: Position, bar: pd.Series) -> tuple[float | None, str | None]:
    """Return (exit_price, reason) if `bar` would exit `pos`, else (None, None)."""
    high = float(bar["high"])
    low = float(bar["low"])
    close = float(bar["close"])

    if pos.direction == "long":
        sl_hit = low <= pos.stop_loss
        tp_hit = high >= pos.take_profit
        if sl_hit and tp_hit:
            return pos.stop_loss, "stop_loss"
        if sl_hit:
            return pos.stop_loss, "stop_loss"
        if tp_hit:
            return pos.take_profit, "take_profit"
        if close < pos.zone.bottom:
            return close, "zone_break"
    else:
        sl_hit = high >= pos.stop_loss
        tp_hit = low <= pos.take_profit
        if sl_hit and tp_hit:
            return pos.stop_loss, "stop_loss"
        if sl_hit:
            return pos.stop_loss, "stop_loss"
        if tp_hit:
            return pos.take_profit, "take_profit"
        if close > pos.zone.top:
            return close, "zone_break"

    return None, None


def _max_drawdown_pct(equity_curve: list[dict]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]["equity"]
    max_dd = 0.0
    for point in equity_curve:
        e = point["equity"]
        if e > peak:
            peak = e
        if peak > 0:
            dd = (peak - e) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd * 100.0


def run_backtest(
    symbols: list[str],
    start: date,
    end: date,
    initial_equity: float = 10_000.0,
    risk_pct: float = 0.02,
    sl_buffer_pct: float = 0.001,
    pivot_lookback_weeks: int = 100,
    cluster_pct: float = 0.005,
    early_exit_mode: str = "none",
    early_exit_min_bars: int = 10,
    early_exit_threshold_r: float = 0.3,
    daily_data: dict[str, pd.DataFrame] | None = None,
    db=None,
) -> BacktestOutput:
    """Run the swing-zone strategy across `symbols` over [start, end].

    `daily_data` lets callers (tests) inject pre-built bars and skip yfinance.
    `early_exit_mode` enables Phase-1b discretionary exit variants (see
    `_evaluate_early_exit`).
    """
    if early_exit_mode not in EARLY_EXIT_MODES:
        raise ValueError(f"early_exit_mode must be one of {EARLY_EXIT_MODES}")
    if daily_data is None:
        daily_data = {
            s: fetch_daily_bars(s, start, end, db=db) for s in symbols
        }
    weekly_data = {s: resample_to_weekly(daily_data[s]) for s in symbols}

    all_dates_set: set[date] = set()
    for df in daily_data.values():
        if not df.empty:
            all_dates_set.update(df["date"].tolist())
    all_dates = sorted(all_dates_set)

    state = {s: SymbolState() for s in symbols}
    equity = initial_equity
    equity_curve: list[dict] = []
    trades_log: list[dict] = []

    daily_indexed = {
        s: df.set_index("date") if not df.empty else df
        for s, df in daily_data.items()
    }

    for current_date in all_dates:
        for sym in symbols:
            df_idx = daily_indexed[sym]
            if df_idx.empty or current_date not in df_idx.index:
                continue
            today_bar = df_idx.loc[current_date]

            prior_idx = df_idx.index[df_idx.index < current_date]
            prev_bar = df_idx.loc[prior_idx[-1]] if len(prior_idx) > 0 else None

            iso = current_date.isocalendar()
            iso_key = (iso[0], iso[1])
            if state[sym].last_rebuild_iso != iso_key:
                # Use only weekly bars completed strictly before this week.
                week_monday = current_date - timedelta(days=current_date.weekday())
                weekly_history = weekly_data[sym][weekly_data[sym]["date"] < week_monday]
                state[sym].zones = build_zones(
                    weekly_history,
                    lookback_weeks=pivot_lookback_weeks,
                    cluster_pct=cluster_pct,
                )
                state[sym].armed.clear()
                state[sym].last_rebuild_iso = iso_key

            # 1. Resolve any open position against today's bar.
            if state[sym].position is not None:
                pos = state[sym].position
                pos.bars_open += 1
                exit_price, reason = _evaluate_exit(pos, today_bar)
                if exit_price is None:
                    exit_price, reason = _evaluate_early_exit(
                        pos,
                        float(today_bar["close"]),
                        early_exit_mode,
                        early_exit_min_bars,
                        early_exit_threshold_r,
                    )
                if exit_price is not None:
                    direction_sign = 1.0 if pos.direction == "long" else -1.0
                    pnl_quote = (exit_price - pos.entry_price) * direction_sign * pos.units
                    pnl_usd = quote_to_usd(pnl_quote, sym, exit_price)
                    equity += pnl_usd
                    trades_log.append({
                        "symbol": sym,
                        "direction": pos.direction,
                        "entry_date": str(pos.entry_date),
                        "exit_date": str(current_date),
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "stop_loss": pos.stop_loss,
                        "take_profit": pos.take_profit,
                        "units": pos.units,
                        "pnl_usd": pnl_usd,
                        "exit_reason": reason,
                        "zone_top": pos.zone.top,
                        "zone_bottom": pos.zone.bottom,
                    })
                    state[sym].position = None

            # 2. Execute pending entry at today's open (if no position).
            if state[sym].position is None and state[sym].pending_entry is not None:
                zone, direction = state[sym].pending_entry
                entry_price = float(today_bar["open"])
                if direction == "long":
                    sl = zone.bottom * (1.0 - sl_buffer_pct)
                    tp = entry_price + (entry_price - sl)
                    valid = sl < entry_price < tp
                else:
                    sl = zone.top * (1.0 + sl_buffer_pct)
                    tp = entry_price - (sl - entry_price)
                    valid = sl > entry_price > tp

                sl_dist_quote = abs(entry_price - sl)
                if valid and sl_dist_quote > 0:
                    risk_usd = equity * risk_pct
                    sl_dist_usd_per_unit = quote_to_usd(sl_dist_quote, sym, entry_price)
                    units = risk_usd / sl_dist_usd_per_unit if sl_dist_usd_per_unit > 0 else 0.0
                    if units > 0:
                        state[sym].position = Position(
                            symbol=sym,
                            direction=direction,
                            entry_date=current_date,
                            entry_price=entry_price,
                            stop_loss=sl,
                            take_profit=tp,
                            units=units,
                            zone=zone,
                        )
                state[sym].pending_entry = None

            # 3. Update arm/disarm state on today's close.
            close = float(today_bar["close"])
            for i, zone in enumerate(state[sym].zones):
                if zone.kind == "support" and close <= zone.midpoint:
                    state[sym].armed.add(i)
                elif zone.kind == "resistance" and close >= zone.midpoint:
                    state[sym].armed.add(i)
            for i in list(state[sym].armed):
                zone = state[sym].zones[i]
                if zone.kind == "support" and close < zone.bottom:
                    state[sym].armed.discard(i)
                elif zone.kind == "resistance" and close > zone.top:
                    state[sym].armed.discard(i)

            # 4. Pattern check on today's candle → queue entry for next open.
            if (
                state[sym].position is None
                and state[sym].pending_entry is None
                and state[sym].armed
            ):
                curr_candle = Candle(
                    open=float(today_bar["open"]),
                    high=float(today_bar["high"]),
                    low=float(today_bar["low"]),
                    close=float(today_bar["close"]),
                )
                prev_candle = None
                if prev_bar is not None:
                    prev_candle = Candle(
                        open=float(prev_bar["open"]),
                        high=float(prev_bar["high"]),
                        low=float(prev_bar["low"]),
                        close=float(prev_bar["close"]),
                    )
                for i in sorted(state[sym].armed):
                    zone = state[sym].zones[i]
                    if zone.kind == "support" and detect_bullish_reversal(prev_candle, curr_candle):
                        state[sym].pending_entry = (zone, "long")
                        break
                    if zone.kind == "resistance" and detect_bearish_reversal(prev_candle, curr_candle):
                        state[sym].pending_entry = (zone, "short")
                        break

        # Curve tracks realized equity only — mark-to-market on multi-pair
        # concurrent positions can dip transiently below zero before SLs fire,
        # which would destroy the drawdown calc. Realized equity is bounded.
        equity_curve.append({"date": str(current_date), "equity": equity})

    # Force-close any still-open positions at the last available close.
    for sym in symbols:
        pos = state[sym].position
        if pos is None:
            continue
        df_idx = daily_indexed[sym]
        if df_idx.empty:
            continue
        last_date = df_idx.index[-1]
        cp = float(df_idx.loc[last_date]["close"])
        direction_sign = 1.0 if pos.direction == "long" else -1.0
        pnl_quote = (cp - pos.entry_price) * direction_sign * pos.units
        pnl_usd = quote_to_usd(pnl_quote, sym, cp)
        equity += pnl_usd
        trades_log.append({
            "symbol": sym,
            "direction": pos.direction,
            "entry_date": str(pos.entry_date),
            "exit_date": str(last_date),
            "entry_price": pos.entry_price,
            "exit_price": cp,
            "stop_loss": pos.stop_loss,
            "take_profit": pos.take_profit,
            "units": pos.units,
            "pnl_usd": pnl_usd,
            "exit_reason": "backtest_end",
            "zone_top": pos.zone.top,
            "zone_bottom": pos.zone.bottom,
        })

    wins = [t for t in trades_log if t["pnl_usd"] > 0]
    losses = [t for t in trades_log if t["pnl_usd"] <= 0]
    gross_win = sum(t["pnl_usd"] for t in wins)
    gross_loss = abs(sum(t["pnl_usd"] for t in losses))
    profit_factor = gross_win / gross_loss if gross_loss > 0 else (
        float("inf") if gross_win > 0 else 0.0
    )
    win_rate = (len(wins) / len(trades_log) * 100.0) if trades_log else 0.0
    total_return = ((equity - initial_equity) / initial_equity * 100.0) if initial_equity > 0 else 0.0

    return BacktestOutput(
        final_equity=equity,
        total_return_pct=total_return,
        total_trades=len(trades_log),
        win_rate_pct=win_rate,
        profit_factor=profit_factor if profit_factor != float("inf") else 9999.0,
        max_drawdown_pct=_max_drawdown_pct(equity_curve),
        equity_curve=equity_curve,
        trades_log=trades_log,
    )
