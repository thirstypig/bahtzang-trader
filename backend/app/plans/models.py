"""Plan database models — plans and plan snapshots.

067-fix: PlanTrade has been merged into the unified Trade table in app.models.
         Use Trade with plan_id filter instead of PlanTrade.
071-fix: Money fields use Numeric(14,4) for exact decimal arithmetic.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer,
    Numeric, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

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
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class PlanSnapshot(Base):
    __tablename__ = "plan_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plans.id", ondelete="CASCADE"), nullable=False,
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
        Index("ix_plan_snapshots_plan_date", "plan_id", date.desc()),
        UniqueConstraint("plan_id", "date", name="uq_plan_snapshots_plan_date"),
    )
