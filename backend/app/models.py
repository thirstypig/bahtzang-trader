"""SQLAlchemy models for the trades database.

067-fix: Trade and PlanTrade unified into a single Trade table.
         portfolio_id=NULL means legacy/global trade; portfolio_id=N means portfolio trade.
071-fix: Money fields use Numeric(14,4) for exact decimal arithmetic.
072-fix: Plans renamed to Portfolios. Strategy rules now per-portfolio.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Index, Integer,
    Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Import feature module models so create_all() picks them up
from app.backtest.models import BacktestConfig, BacktestResult, OHLCVCache  # noqa: F401
from app.earnings.models import EarningsEvent  # noqa: F401
from app.forex.models import ForexBacktestRun, ForexBar  # noqa: F401
from app.plans.models import (  # noqa: F401
    Portfolio, PlanSnapshot, PortfolioTouchHistory, PortfolioStrategyAudit
)


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

    # 067-fix: portfolio_id links trade to a portfolio. NULL = legacy/global trade.
    portfolio_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("portfolios.id", ondelete="RESTRICT"), nullable=True,
    )
    # 080-fix: Alpaca order ID for reconciliation
    alpaca_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 071-fix: Numeric for virtual cash tracking
    virtual_cash_before: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    virtual_cash_after: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)

    __table_args__ = (
        Index("ix_trades_timestamp_executed", "timestamp", "executed"),
        Index("ix_trades_timestamp_desc", timestamp.desc()),
        # Portfolio-scoped indexes (072-fix: renamed from plan_id)
        Index("ix_trades_portfolio_timestamp", "portfolio_id", timestamp.desc()),
        Index("ix_trades_portfolio_ticker", "portfolio_id", "ticker", "timestamp"),
        Index("ix_trades_portfolio_executed", "portfolio_id", "executed", "timestamp"),
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
        # Include portfolio fields only for portfolio trades
        if self.portfolio_id is not None:
            d["portfolio_id"] = self.portfolio_id
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


# GuardrailsConfig + GuardrailsAudit removed in the portfolio-only consolidation.
# Per-portfolio strategy lives on Portfolio (app/plans/models.py); rule-change
# audit lives in portfolio_strategy_audit. See migration 076.
