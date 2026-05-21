"""Screener tables: one ScreenerRun per refresh, with its ranked candidates."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ScreenerRun(Base):
    """A single screening pass over the universe."""

    __tablename__ = "screener_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    universe_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scored_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")  # running/complete/failed
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    candidates: Mapped[list["ScreenerCandidate"]] = relationship(
        back_populates="run", cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_screener_runs_run_at", run_at.desc()),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_at": self.run_at.isoformat(),
            "universe_size": self.universe_size,
            "scored_count": self.scored_count,
            "status": self.status,
            "error": self.error,
        }


class ScreenerCandidate(Base):
    """One ranked ticker within a ScreenerRun, with its factor breakdown."""

    __tablename__ = "screener_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("screener_runs.id", ondelete="CASCADE"), nullable=False,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    # Factor breakdown (raw values, for display + transparency)
    momentum: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rel_strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trend_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rsi: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    volatility: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    run: Mapped["ScreenerRun"] = relationship(back_populates="candidates")

    __table_args__ = (
        Index("ix_screener_candidates_run_rank", "run_id", "rank"),
    )

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "ticker": self.ticker,
            "composite_score": round(self.composite_score, 3),
            "momentum": round(self.momentum, 4),
            "rel_strength": round(self.rel_strength, 4),
            "trend_score": round(self.trend_score, 2),
            "rsi": round(self.rsi, 1),
            "volatility": round(self.volatility, 4),
            "price": round(self.price, 2),
        }
