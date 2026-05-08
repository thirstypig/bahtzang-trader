"""Portfolio database models — portfolios, snapshots, touch history, and audit logs.

067-fix: PlanTrade has been merged into the unified Trade table in app.models.
         Use Trade with portfolio_id filter instead of PlanTrade.
071-fix: Money fields use Numeric(14,4) for exact decimal arithmetic.
072-fix: Plans renamed to Portfolios. Strategy rules now per-portfolio, not global.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer,
    Numeric, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 071-fix: Numeric for exact arithmetic
    budget: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    virtual_cash: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    trading_goal: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_profile: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    trading_frequency: Mapped[str] = mapped_column(String(10), nullable=False, default="1x")
    target_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    target_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Strategy rules (per-portfolio, not global)
    cooldown_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    min_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.55"))
    respect_wash_sale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    kelly_fraction: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("0.15"))
    circuit_breaker_daily_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("-5.0"))
    circuit_breaker_weekly_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("-10.0"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "budget": float(self.budget),
            "virtual_cash": float(self.virtual_cash),
            "trading_goal": self.trading_goal,
            "risk_profile": self.risk_profile,
            "trading_frequency": self.trading_frequency,
            "target_amount": float(self.target_amount) if self.target_amount is not None else None,
            "target_date": self.target_date,
            "is_active": self.is_active,
            "cooldown_hours": self.cooldown_hours,
            "min_confidence": float(self.min_confidence),
            "respect_wash_sale": self.respect_wash_sale,
            "kelly_fraction": float(self.kelly_fraction),
            "circuit_breaker_daily_pct": float(self.circuit_breaker_daily_pct),
            "circuit_breaker_weekly_pct": float(self.circuit_breaker_weekly_pct),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class PlanSnapshot(Base):
    __tablename__ = "plan_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # 071-fix: Numeric for exact arithmetic
    budget: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    virtual_cash: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    invested_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    pnl: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    pnl_pct: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)

    __table_args__ = (
        Index("ix_portfolio_snapshots_portfolio_date", "portfolio_id", date.desc()),
        UniqueConstraint("portfolio_id", "date", name="uq_plan_snapshots_portfolio_date"),
    )


class PortfolioTouchHistory(Base):
    """Tracks per-ticker trading history to enforce cooldown and frequency rules.

    Each row represents the last time (and last action) a ticker was touched within
    a specific portfolio. Used by the trading constraints checker to prevent:
    - Repetitive trading on same ticker (cooldown enforcement)
    - Excessive frequency on same ticker (5 buys + 5 sells per week)
    - Same action twice in a row (buy/buy or sell/sell prevention)
    """
    __tablename__ = "portfolio_touch_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    last_decision_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    last_action: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("portfolio_id", "ticker", name="uq_portfolio_touch_history_portfolio_ticker"),
        Index("ix_portfolio_touch_history_portfolio", "portfolio_id", "ticker"),
    )


class PortfolioStrategyAudit(Base):
    """Audit log for strategy rule changes within a portfolio.

    Every time a user changes a strategy rule (cooldown, confidence, kelly_fraction, etc.),
    this table records: who changed it, what changed, old/new values, when, and why.
    Enables users to correlate rule changes with trading performance.
    """
    __tablename__ = "portfolio_strategy_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False,
    )
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_portfolio_strategy_audit_portfolio_timestamp", "portfolio_id", timestamp.desc()),
        Index("ix_portfolio_strategy_audit_action", "portfolio_id", "action", timestamp.desc()),
        Index("ix_portfolio_strategy_audit_user", "user_email", timestamp.desc()),
    )
