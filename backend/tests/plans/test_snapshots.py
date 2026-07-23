"""Unit tests for plan snapshots — daily portfolio valuation capture."""

import pytest
from unittest.mock import patch, AsyncMock
from datetime import date, timedelta

from app.plans.models import PlanSnapshot, TickerPrice
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
        with patch("app.plans.snapshots.get_indicators", new=AsyncMock(return_value={})):
            count = await take_plan_snapshots(db_session)

        assert count == 1
        snap = db_session.query(PlanSnapshot).filter_by(portfolio_id=plan.id).first()
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

        with patch("app.plans.snapshots.get_indicators", new=AsyncMock(
            return_value={"AAPL": {"price": 160.0}}
        )):
            count = await take_plan_snapshots(db_session)

        assert count == 1
        snap = db_session.query(PlanSnapshot).filter_by(portfolio_id=plan.id).first()
        assert snap.invested_value == 1600.0  # 10 shares * $160
        assert snap.total_value == 6600.0     # $1600 + $5000 cash
        assert snap.pnl == pytest.approx(-3400.0)  # $6600 - $10000 budget

    @pytest.mark.asyncio
    async def test_snapshot_upsert_same_day(self, db_session):
        """Running snapshots twice in one day should update, not duplicate."""
        plan = make_plan(db_session, budget=5000, virtual_cash=5000)

        with patch("app.plans.snapshots.get_indicators", new=AsyncMock(return_value={})):
            await take_plan_snapshots(db_session)
            await take_plan_snapshots(db_session)

        snaps = db_session.query(PlanSnapshot).filter_by(portfolio_id=plan.id).all()
        assert len(snaps) == 1  # upsert, not duplicate

    @pytest.mark.asyncio
    async def test_skips_inactive_plans(self, db_session):
        make_plan(db_session, is_active=False)
        with patch("app.plans.snapshots.get_indicators", new=AsyncMock(return_value={})):
            count = await take_plan_snapshots(db_session)
        assert count == 0


@pytest.mark.integration
class TestMissingPriceHandling:
    """A price we cannot fetch must never be treated as a price of $0.

    Regression: prod snapshots valued held positions at $0 whenever the quote
    source dropped a ticker, fabricating a -40.8% drawdown on a portfolio that
    was actually down 7.5%. The Phase G zero-losing-weeks gate reads this table,
    so a phantom loss here is a false gate failure.
    """

    @pytest.mark.asyncio
    async def test_position_priced_from_alpaca_when_quote_source_drops_ticker(
        self, db_session
    ):
        plan = make_plan(db_session, budget=10000, virtual_cash=5000)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy",
                   quantity=10, price=150)

        # Alpha Vantage rate-limited: the ticker is silently absent.
        with patch("app.plans.snapshots.get_indicators", new=AsyncMock(
            return_value={"AAPL": {"price": 160.0}}
        )):
            count = await take_plan_snapshots(db_session)

        assert count == 1
        snap = db_session.query(PlanSnapshot).filter_by(portfolio_id=plan.id).first()
        assert snap.invested_value == 1600.0, (
            "held position was valued at $0 because its price was missing"
        )
        assert snap.total_value == 6600.0

    @pytest.mark.asyncio
    async def test_records_price_so_it_can_be_carried_forward(self, db_session):
        plan = make_plan(db_session, budget=10000, virtual_cash=5000)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy",
                   quantity=10, price=150)

        with patch("app.plans.snapshots.get_indicators", new=AsyncMock(
            return_value={"AAPL": {"price": 160.0}}
        )):
            await take_plan_snapshots(db_session)

        cached = db_session.query(TickerPrice).filter_by(ticker="AAPL").one()
        assert cached.price == 160.0
        assert cached.as_of == date.today()

    @pytest.mark.asyncio
    async def test_carries_forward_last_known_price_when_source_is_down(
        self, db_session
    ):
        """Total outage: value the position at its last known price, not $0."""
        plan = make_plan(db_session, budget=10000, virtual_cash=5000)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy",
                   quantity=10, price=150)
        db_session.add(TickerPrice(
            ticker="AAPL", price=160.0, as_of=date.today() - timedelta(days=1),
        ))
        db_session.commit()

        with patch("app.plans.snapshots.get_indicators", new=AsyncMock(return_value={})):
            count = await take_plan_snapshots(db_session)

        assert count == 1
        snap = db_session.query(PlanSnapshot).filter_by(portfolio_id=plan.id).first()
        assert snap.invested_value == 1600.0
        assert snap.total_value == 6600.0

    @pytest.mark.asyncio
    async def test_skips_snapshot_when_carry_forward_price_is_too_stale(
        self, db_session
    ):
        """A price this old is not evidence. Write no row rather than a wrong one.

        Bounding staleness is what stops a genuine multi-day crash from being
        masked by an indefinitely repeated last-good price.
        """
        plan = make_plan(db_session, budget=10000, virtual_cash=5000)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy",
                   quantity=10, price=150)
        db_session.add(TickerPrice(
            ticker="AAPL", price=160.0, as_of=date.today() - timedelta(days=30),
        ))
        db_session.commit()

        with patch("app.plans.snapshots.get_indicators", new=AsyncMock(return_value={})):
            count = await take_plan_snapshots(db_session)

        assert count == 0
        assert db_session.query(PlanSnapshot).filter_by(portfolio_id=plan.id).count() == 0

    @pytest.mark.asyncio
    async def test_skips_snapshot_when_position_has_no_price_at_all(self, db_session):
        """Never fabricate a valuation for a position we have never priced."""
        plan = make_plan(db_session, budget=10000, virtual_cash=5000)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy",
                   quantity=10, price=150)

        with patch("app.plans.snapshots.get_indicators", new=AsyncMock(return_value={})):
            count = await take_plan_snapshots(db_session)

        assert count == 0
        assert db_session.query(PlanSnapshot).filter_by(portfolio_id=plan.id).count() == 0
