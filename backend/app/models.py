"""SQLAlchemy models for the trades database.

067-fix: Trade and PlanTrade unified into a single Trade table.
         plan_id=NULL means legacy/global trade; plan_id=N means plan trade.
071-fix: Money fields use Numeric(14,4) for exact decimal arithmetic.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Index, Integer,
    Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database import Base

# Import feature module models so create_all() picks them up
from app.backtest.models import BacktestConfig, BacktestResult, OHLCVCache  # noqa: F401
from app.earnings.models import EarningsEvent  # noqa: F401
from app.plans.models import Plan, PlanSnapshot  # noqa: F401


class Trade(Base):
    """Unified trade table for both global and plan-scoped trades.

    067-fix: Merged PlanTrade into Trade. plan_id=NULL for legacy trades,
    plan_id=N for plan trades. This eliminates the duplicate model and
    ensures tax exports, analytics, and bug fixes apply to all trades.

    071-fix: price, virtual_cash_before/after use Numeric for exact arithmetic.
    """
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # buy/sell/hold
    # 067-fix: Float (was Integer) — fractional shares supported
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    # 071-fix: Numeric for exact decimal arithmetic on money
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    claude_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    guardrail_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    guardrail_block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 067-fix: plan_id links trade to a plan. NULL = legacy/global trade.
    plan_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=True,
    )
    # 080-fix: Alpaca order ID for reconciliation
    alpaca_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 071-fix: Numeric for virtual cash tracking
    virtual_cash_before: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    virtual_cash_after: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)

    __table_args__ = (
        Index("ix_trades_timestamp_executed", "timestamp", "executed"),
        Index("ix_trades_timestamp_desc", timestamp.desc()),
        # Plan-scoped indexes (067-fix)
        Index("ix_trades_plan_timestamp", "plan_id", timestamp.desc()),
        Index("ix_trades_plan_ticker", "plan_id", "ticker", "timestamp"),
        Index("ix_trades_plan_executed", "plan_id", "executed", "timestamp"),
    )

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "ticker": self.ticker,
            "action": self.action,
            "quantity": self.quantity,
            "price": float(self.price) if self.price is not None else None,
            "claude_reasoning": self.claude_reasoning,
            "confidence": self.confidence,
            "guardrail_passed": self.guardrail_passed,
            "guardrail_block_reason": self.guardrail_block_reason,
            "executed": self.executed,
        }
        # Include plan fields only for plan trades
        if self.plan_id is not None:
            d["plan_id"] = self.plan_id
            d["alpaca_order_id"] = self.alpaca_order_id
            d["virtual_cash_before"] = float(self.virtual_cash_before) if self.virtual_cash_before is not None else None
            d["virtual_cash_after"] = float(self.virtual_cash_after) if self.virtual_cash_after is not None else None
        return d


class PortfolioSnapshot(Base):
    """Daily portfolio state captured at market close (4:05 PM ET)."""
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(Date, unique=True, nullable=False)
    # 071-fix: Numeric for exact arithmetic
    total_equity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    invested: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    spy_close: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    deposit_withdrawal: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)

    __table_args__ = (
        Index("ix_snapshots_date", "date"),
    )

    def to_dict(self) -> dict:
        return {
            "date": str(self.date),
            "total_equity": float(self.total_equity),
            "cash": float(self.cash),
            "invested": float(self.invested),
            "unrealized_pnl": float(self.unrealized_pnl),
            "spy_close": float(self.spy_close) if self.spy_close is not None else None,
            "deposit_withdrawal": float(self.deposit_withdrawal),
        }


class GuardrailsConfig(Base):
    """Single-row table storing guardrails configuration."""
    __tablename__ = "guardrails_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    risk_profile: Mapped[str] = mapped_column(String(20), default="moderate")
    trading_goal: Mapped[str] = mapped_column(String(30), default="maximize_returns")
    trading_frequency: Mapped[str] = mapped_column(String(5), default="1x")
    # 071-fix: Numeric for money fields
    max_total_invested: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=5000)
    max_single_trade_size: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=1000)
    stop_loss_threshold: Mapped[float] = mapped_column(Float, default=0.05)
    daily_order_limit: Mapped[int] = mapped_column(Integer, default=2)
    min_confidence: Mapped[float] = mapped_column(Float, default=0.60)
    max_positions: Mapped[int] = mapped_column(Integer, default=5)
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    kelly_fraction: Mapped[float] = mapped_column(Float, default=0.25)
    circuit_breaker_daily_pct: Mapped[float] = mapped_column(Float, default=0.05)
    circuit_breaker_weekly_pct: Mapped[float] = mapped_column(Float, default=0.10)
    respect_wash_sale: Mapped[bool] = mapped_column(Boolean, default=True)
    pdt_protection: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_dict(self) -> dict:
        return {
            "risk_profile": self.risk_profile,
            "trading_goal": self.trading_goal,
            "trading_frequency": self.trading_frequency,
            "max_total_invested": float(self.max_total_invested),
            "max_single_trade_size": float(self.max_single_trade_size),
            "stop_loss_threshold": self.stop_loss_threshold,
            "daily_order_limit": self.daily_order_limit,
            "min_confidence": self.min_confidence,
            "max_positions": self.max_positions,
            "kill_switch": self.kill_switch,
            "kelly_fraction": self.kelly_fraction,
            "circuit_breaker_daily_pct": self.circuit_breaker_daily_pct,
            "circuit_breaker_weekly_pct": self.circuit_breaker_weekly_pct,
            "respect_wash_sale": self.respect_wash_sale,
            "pdt_protection": self.pdt_protection,
        }

    @staticmethod
    def get_or_create(db: Session) -> "GuardrailsConfig":
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
