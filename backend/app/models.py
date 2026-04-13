"""SQLAlchemy models for the trades database."""

import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 008-fix: Use timezone-aware datetime instead of deprecated utcnow
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # buy/sell/hold
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    claude_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    guardrail_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    guardrail_block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 020-fix: Add indexes for common query patterns
    __table_args__ = (
        Index("ix_trades_timestamp_executed", "timestamp", "executed"),
        Index("ix_trades_timestamp_desc", timestamp.desc()),
    )


class PortfolioSnapshot(Base):
    """Daily portfolio state captured at market close (4:05 PM ET)."""
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(Date, unique=True, nullable=False)
    total_equity: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    invested: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    spy_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    deposit_withdrawal: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        Index("ix_snapshots_date", "date"),
    )

    def to_dict(self) -> dict:
        return {
            "date": str(self.date),
            "total_equity": self.total_equity,
            "cash": self.cash,
            "invested": self.invested,
            "unrealized_pnl": self.unrealized_pnl,
            "spy_close": self.spy_close,
            "deposit_withdrawal": self.deposit_withdrawal,
        }


class GuardrailsConfig(Base):
    """Single-row table storing guardrails configuration.

    Replaces the guardrails.json file so config persists across
    Railway deploys and is safe under concurrent access.
    """
    __tablename__ = "guardrails_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    risk_profile: Mapped[str] = mapped_column(String(20), default="moderate")
    trading_goal: Mapped[str] = mapped_column(String(30), default="maximize_returns")
    trading_frequency: Mapped[str] = mapped_column(String(5), default="1x")
    max_total_invested: Mapped[float] = mapped_column(Float, default=60000)
    max_single_trade_size: Mapped[float] = mapped_column(Float, default=10000)
    stop_loss_threshold: Mapped[float] = mapped_column(Float, default=0.05)
    daily_order_limit: Mapped[int] = mapped_column(Integer, default=5)
    min_confidence: Mapped[float] = mapped_column(Float, default=0.60)
    max_positions: Mapped[int] = mapped_column(Integer, default=10)
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "risk_profile": self.risk_profile,
            "trading_goal": self.trading_goal,
            "trading_frequency": self.trading_frequency,
            "max_total_invested": self.max_total_invested,
            "max_single_trade_size": self.max_single_trade_size,
            "stop_loss_threshold": self.stop_loss_threshold,
            "daily_order_limit": self.daily_order_limit,
            "min_confidence": self.min_confidence,
            "max_positions": self.max_positions,
            "kill_switch": self.kill_switch,
        }

    @staticmethod
    def get_or_create(db: Session) -> "GuardrailsConfig":
        """Get the single config row, creating it with defaults if missing."""
        config = db.query(GuardrailsConfig).filter_by(id=1).first()
        if config is None:
            config = GuardrailsConfig(id=1)
            db.add(config)
            db.commit()
            db.refresh(config)
        return config


class GuardrailsAudit(Base):
    """Audit log for guardrails configuration changes."""
    __tablename__ = "guardrails_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    changes: Mapped[str] = mapped_column(Text, nullable=False)

    @staticmethod
    def log(db: Session, email: str, action: str, changes: dict):
        entry = GuardrailsAudit(
            user_email=email,
            action=action,
            changes=json.dumps(changes),
        )
        db.add(entry)
        db.commit()
