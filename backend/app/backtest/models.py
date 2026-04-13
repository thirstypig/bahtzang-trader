"""Backtest database models — config, results, and OHLCV cache."""

import json
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BacktestConfig(Base):
    __tablename__ = "backtest_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    tickers: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False, default=100000)
    params: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    max_position_pct: Mapped[float] = mapped_column(Float, default=0.10)
    max_positions: Mapped[int] = mapped_column(Integer, default=10)
    stop_loss_pct: Mapped[float] = mapped_column(Float, default=0.05)

    def get_tickers(self) -> list[str]:
        return json.loads(self.tickers)

    def get_params(self) -> dict:
        return json.loads(self.params)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "strategy": self.strategy,
            "tickers": self.get_tickers(),
            "start_date": str(self.start_date),
            "end_date": str(self.end_date),
            "initial_capital": self.initial_capital,
            "params": self.get_params(),
            "max_position_pct": self.max_position_pct,
            "max_positions": self.max_positions,
            "stop_loss_pct": self.stop_loss_pct,
        }


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Metrics
    total_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Full results as JSON
    equity_curve: Mapped[str | None] = mapped_column(Text, nullable=True)
    trades_log: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_backtest_results_config", "config_id"),
    )

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "config_id": self.config_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "total_return_pct": self.total_return_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown_pct": self.max_drawdown_pct,
            "win_rate_pct": self.win_rate_pct,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
        }

    def to_detail(self) -> dict:
        d = self.to_summary()
        d["equity_curve"] = json.loads(self.equity_curve) if self.equity_curve else []
        d["trades_log"] = json.loads(self.trades_log) if self.trades_log else []
        return d


class OHLCVCache(Base):
    """Cached daily OHLCV bars from Alpaca."""
    __tablename__ = "ohlcv_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    bar_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_ohlcv_ticker_date", "ticker", "bar_date", unique=True),
    )
