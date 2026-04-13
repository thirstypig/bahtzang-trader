"""Earnings calendar database model."""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EarningsEvent(Base):
    """Cached earnings calendar data from Finnhub."""
    __tablename__ = "earnings_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_quarter: Mapped[str | None] = mapped_column(String(10), nullable=True)
    eps_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    hour: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "bmo" or "amc"
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_earnings_symbol_date", "symbol", "report_date"),
        Index("ix_earnings_report_date", "report_date"),
    )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "report_date": str(self.report_date),
            "fiscal_quarter": self.fiscal_quarter,
            "eps_estimate": self.eps_estimate,
            "revenue_estimate": self.revenue_estimate,
            "hour": self.hour,
        }
