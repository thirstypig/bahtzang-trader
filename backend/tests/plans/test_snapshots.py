"""Unit tests for plan snapshots — daily portfolio valuation capture."""

import pytest
from unittest.mock import patch, AsyncMock
from datetime import date

from app.plans.models import PlanSnapshot
from app.plans.snapshots import take_plan_snapshots
from tests.conftest import make_plan, make_trade


@pytest.mark.integration
class TestTakePlanSnapshots:
    @pytest.mark.asyncio
    async def test_no_active_plans(self, db_session):
        count = await take_plan_snapshots(db_session)
        assert count == 0

    @pytest.mark.asyncio
    async def test_snapshot_new_plan_no_positions(self, db_session):
        plan = make_plan(db_session, budget=5000, virtual_cash=5000)
        with patch("app.plans.snapshots.market_data") as mock_md:
            mock_md.get_quotes = AsyncMock(return_value=[])
            count = await take_plan_snapshots(db_session)

        assert count == 1
        snap = db_session.query(PlanSnapshot).filter_by(plan_id=plan.id).first()
        assert snap is not None
        assert snap.budget == 5000
        assert snap.virtual_cash == 5000
        assert snap.invested_value == 0
        assert snap.total_value == 5000  # just cash
        assert snap.pnl == 0

    @pytest.mark.asyncio
    async def test_snapshot_with_positions(self, db_session):
        plan = make_plan(db_session, budget=10000, virtual_cash=5000)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy",
                   quantity=10, price=150)

        with patch("app.plans.snapshots.market_data") as mock_md:
            mock_md.get_quotes = AsyncMock(return_value=[
                {"ticker": "AAPL", "price": 160.0},
            ])
            count = await take_plan_snapshots(db_session)

        assert count == 1
        snap = db_session.query(PlanSnapshot).filter_by(plan_id=plan.id).first()
        assert snap.invested_value == 1600.0  # 10 shares * $160
        assert snap.total_value == 6600.0     # $1600 + $5000 cash
        assert snap.pnl == pytest.approx(-3400.0)  # $6600 - $10000 budget

    @pytest.mark.asyncio
    async def test_snapshot_upsert_same_day(self, db_session):
        """Running snapshots twice in one day should update, not duplicate."""
        plan = make_plan(db_session, budget=5000, virtual_cash=5000)

        with patch("app.plans.snapshots.market_data") as mock_md:
            mock_md.get_quotes = AsyncMock(return_value=[])
            await take_plan_snapshots(db_session)
            await take_plan_snapshots(db_session)

        snaps = db_session.query(PlanSnapshot).filter_by(plan_id=plan.id).all()
        assert len(snaps) == 1  # upsert, not duplicate

    @pytest.mark.asyncio
    async def test_skips_inactive_plans(self, db_session):
        make_plan(db_session, is_active=False)
        with patch("app.plans.snapshots.market_data") as mock_md:
            mock_md.get_quotes = AsyncMock(return_value=[])
            count = await take_plan_snapshots(db_session)
        assert count == 0
