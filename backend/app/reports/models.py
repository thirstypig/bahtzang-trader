"""Saved weekly reports — one row per week (re-running a week replaces it)."""

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    week_ending: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "week_ending": self.week_ending.isoformat(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "portfolios": [
                {k: p.get(k) for k in ("id", "name", "after_cost_return_pct", "spy_return_pct", "beat_spy")}
                for p in (self.payload or {}).get("portfolios", [])
            ],
        }

    def to_detail(self) -> dict:
        return {**self.to_summary(), "payload": self.payload, "note": self.note,
                "note_model": self.note_model}
