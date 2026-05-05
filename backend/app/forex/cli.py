"""CLI runner for the forex backtest — no FastAPI server needed.

Usage:
    python -m app.forex.cli --symbols EURUSD GBPUSD USDJPY \
        --start 2018-01-01 --end 2025-12-31 --equity 10000 --risk 0.02

Prints summary metrics and a small sample of the trades log.
"""

from __future__ import annotations

import argparse
import os
from datetime import date, datetime

# Stub env so the shared config/database chain imports cleanly when running
# this CLI without a real .env. The backtest never touches Anthropic/Supabase/Postgres.
os.environ.setdefault("ANTHROPIC_API_KEY", "cli-stub")
os.environ.setdefault("ALPHA_VANTAGE_KEY", "cli-stub")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SUPABASE_URL", "https://stub.supabase.co")
os.environ.setdefault("ALLOWED_EMAIL", "cli@stub.local")

from app.forex.engine import run_backtest  # noqa: E402


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> None:
    p = argparse.ArgumentParser(description="Forex swing-zone backtest")
    p.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD", "USDJPY"])
    p.add_argument("--start", type=_parse_date, default=_parse_date("2018-01-01"))
    p.add_argument("--end", type=_parse_date, default=_parse_date("2025-12-31"))
    p.add_argument("--equity", type=float, default=10_000.0)
    p.add_argument("--risk", type=float, default=0.02)
    p.add_argument("--sl-buffer", type=float, default=0.001)
    p.add_argument("--lookback-weeks", type=int, default=100)
    p.add_argument("--cluster-pct", type=float, default=0.005)
    p.add_argument("--show-trades", type=int, default=10, help="N most recent trades to print")
    p.add_argument("--early-exit", choices=["none", "progress", "time_band"], default="none")
    p.add_argument("--early-exit-bars", type=int, default=10)
    p.add_argument("--early-exit-threshold", type=float, default=0.3)
    args = p.parse_args()

    print(f"Backtest: {args.symbols}  {args.start} → {args.end}")
    print(f"  equity={args.equity:,.0f}  risk={args.risk*100:.1f}%  sl_buffer={args.sl_buffer*100:.2f}%")
    print(f"  pivot_lookback={args.lookback_weeks}w  cluster_pct={args.cluster_pct*100:.2f}%")
    print(f"  early_exit={args.early_exit} (min_bars={args.early_exit_bars}, threshold_r={args.early_exit_threshold})")
    print()
    print("Fetching daily bars from yfinance (network)...")

    out = run_backtest(
        symbols=[s.upper() for s in args.symbols],
        start=args.start,
        end=args.end,
        initial_equity=args.equity,
        risk_pct=args.risk,
        sl_buffer_pct=args.sl_buffer,
        pivot_lookback_weeks=args.lookback_weeks,
        cluster_pct=args.cluster_pct,
        early_exit_mode=args.early_exit,
        early_exit_min_bars=args.early_exit_bars,
        early_exit_threshold_r=args.early_exit_threshold,
    )

    print()
    print("=" * 60)
    print(f"Final equity:      ${out.final_equity:,.2f}")
    print(f"Total return:      {out.total_return_pct:+.2f}%")
    print(f"Trades:            {out.total_trades}")
    print(f"Win rate:          {out.win_rate_pct:.1f}%")
    print(f"Profit factor:     {out.profit_factor:.2f}")
    print(f"Max drawdown:      {out.max_drawdown_pct:.2f}%")
    print("=" * 60)

    if out.trades_log and args.show_trades > 0:
        print()
        print(f"Last {min(args.show_trades, len(out.trades_log))} trades:")
        for t in out.trades_log[-args.show_trades:]:
            print(
                f"  {t['symbol']} {t['direction']:5s} "
                f"{t['entry_date']} → {t['exit_date']}  "
                f"entry={t['entry_price']:.5f} exit={t['exit_price']:.5f}  "
                f"pnl=${t['pnl_usd']:+.2f}  reason={t['exit_reason']}"
            )


if __name__ == "__main__":
    main()
