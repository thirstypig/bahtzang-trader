"""Plan database models — plans, plan trades, and plan snapshots."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    budget: Mapped[float] = mapped_column(Float, nullable=False)
    virtual_cash: Mapped[float] = mapped_column(Float, nullable=False)
    trading_goal: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_profile: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    trading_frequency: Mapped[str] = mapped_column(String(10), nullable=False, default="1x")
    target_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
            "budget": self.budget,
            "virtual_cash": self.virtual_cash,
            "trading_goal": self.trading_goal,
            "risk_profile": self.risk_profile,
            "trading_frequency": self.trading_frequency,
            "target_amount": self.target_amount,
            "target_date": self.target_date,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class PlanTrade(Base):
    __tablename__ = "plan_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 062-fix: FK with RESTRICT — don't silently orphan trade history on plan delete.
    # Force explicit handling (archive/export) before deleting a plan.
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    claude_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    guardrail_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    guardrail_block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    virtual_cash_before: Mapped[float] = mapped_column(Float, nullable=False)
    virtual_cash_after: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_plan_trades_plan_timestamp", "plan_id", timestamp.desc()),
        Index("ix_plan_trades_plan_ticker", "plan_id", "ticker", "timestamp"),
        Index("ix_plan_trades_plan_executed", "plan_id", "executed", "timestamp"),
        Index("ix_plan_trades_timestamp_desc", timestamp.desc()),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "timestamp": self.timestamp.isoformat(),
            "ticker": self.ticker,
            "action": self.action,
            "quantity": self.quantity,
            "price": self.price,
            "claude_reasoning": self.claude_reasoning,
            "confidence": self.confidence,
            "guardrail_passed": self.guardrail_passed,
            "guardrail_block_reason": self.guardrail_block_reason,
            "executed": self.executed,
            "virtual_cash_before": self.virtual_cash_before,
            "virtual_cash_after": self.virtual_cash_after,
        }


class PlanSnapshot(Base):
    __tablename__ = "plan_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 062-fix: FK with CASCADE — snapshots are derivable, safe to drop on plan delete.
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plans.id", ondelete="CASCADE"), nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    budget: Mapped[float] = mapped_column(Float, nullable=False)
    virtual_cash: Mapped[float] = mapped_column(Float, nullable=False)
    invested_value: Mapped[float] = mapped_column(Float, nullable=False)
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    pnl_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # 070-fix: Unique constraint prevents duplicate snapshots if job runs twice
    __table_args__ = (
        Index("ix_plan_snapshots_plan_date", "plan_id", date.desc()),
        UniqueConstraint("plan_id", "date", name="uq_plan_snapshots_plan_date"),
    )
