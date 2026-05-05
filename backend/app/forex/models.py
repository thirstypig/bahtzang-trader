"""Forex feature: SQLAlchemy models.

Isolated from the existing OHLCVCache because forex symbols (EURUSD=X) and
their pricing semantics are distinct from Alpaca equity tickers.
"""

import json
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ForexBar(Base):
    """Daily OHLCV cache for forex pairs."""

    __tablename__ = "forex_bars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    bar_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_forex_bars_symbol_date", "symbol", "bar_date", unique=True),
    )


class ForexBacktestRun(Base):
    """A single backtest run + its computed metrics + serialized output."""

    __tablename__ = "forex_backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    symbols: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_equity: Mapped[float] = mapped_column(Float, nullable=False, default=10_000.0)
    risk_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.02)
    sl_buffer_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.001)
    pivot_lookback_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    cluster_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.005)
    early_exit_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    early_exit_min_bars: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    early_exit_threshold_r: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)

    # Aggregate metrics
    final_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Full traces (JSON)
    equity_curve: Mapped[str | None] = mapped_column(Text, nullable=True)
    trades_log: Mapped[str | None] = mapped_column(Text, nullable=True)

    def get_symbols(self) -> list[str]:
        return json.loads(self.symbols)

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status,
            "error_message": self.error_message,
            "symbols": self.get_symbols(),
            "start_date": str(self.start_date),
            "end_date": str(self.end_date),
            "initial_equity": self.initial_equity,
            "risk_pct": self.risk_pct,
            "final_equity": self.final_equity,
            "total_return_pct": self.total_return_pct,
            "total_trades": self.total_trades,
            "win_rate_pct": self.win_rate_pct,
            "profit_factor": self.profit_factor,
            "max_drawdown_pct": self.max_drawdown_pct,
        }

    def to_detail(self) -> dict:
        d = self.to_summary()
        d["equity_curve"] = json.loads(self.equity_curve) if self.equity_curve else []
        d["trades_log"] = json.loads(self.trades_log) if self.trades_log else []
        d["sl_buffer_pct"] = self.sl_buffer_pct
        d["pivot_lookback_weeks"] = self.pivot_lookback_weeks
        d["cluster_pct"] = self.cluster_pct
        d["early_exit_mode"] = self.early_exit_mode
        d["early_exit_min_bars"] = self.early_exit_min_bars
        d["early_exit_threshold_r"] = self.early_exit_threshold_r
        return d
