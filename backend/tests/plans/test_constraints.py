"""Tests for trading constraints enforcement (Phase 4)."""

import pytest
from datetime import datetime, timedelta, timezone

from app.models import Trade
from app.plans.constraints import check_trading_constraints, update_touch_history
from app.plans.models import Portfolio, PortfolioTouchHistory


@pytest.fixture
def portfolio(db_session):
	"""Create a test portfolio with default constraints."""
	p = Portfolio(
		name="Test Portfolio",
		budget=10000,
		virtual_cash=10000,
		trading_goal="maximize_returns",
		risk_profile="moderate",
		trading_frequency="1x",
		cooldown_hours=48,
		min_confidence=0.55,
	)
	db_session.add(p)
	db_session.commit()
	db_session.refresh(p)
	return p


@pytest.mark.asyncio
async def test_constraint_check_holds_pass(db_session, portfolio):
	"""HOLD decisions should always pass constraints."""
	decision = {"ticker": "AAPL", "action": "HOLD"}
	now = datetime.now()

	allowed, reason = await check_trading_constraints(db_session, portfolio, decision, now)

	assert allowed is True
	assert reason is None


@pytest.mark.asyncio
async def test_constraint_check_cooldown_enforced(db_session, portfolio):
	"""Cooldown constraint should block trades within the window."""
	# Create a touch history entry 24 hours ago
	touch = PortfolioTouchHistory(
		portfolio_id=portfolio.id,
		ticker="AAPL",
		last_decision_timestamp=datetime.now() - timedelta(hours=24),
		last_action="BUY",
	)
	db_session.add(touch)
	db_session.commit()

	decision = {"ticker": "AAPL", "action": "SELL", "quantity": 10}
	now = datetime.now()

	# Should fail — only 24 hours elapsed, need 48
	allowed, reason = await check_trading_constraints(db_session, portfolio, decision, now)

	assert allowed is False
	assert "Cooldown" in reason
	assert "AAPL" in reason
	assert "24." in reason  # The hours_elapsed value


@pytest.mark.asyncio
async def test_constraint_check_cooldown_passes_after_window(db_session, portfolio):
	"""Cooldown should pass after the minimum hours have elapsed."""
	# Create a touch history entry 49 hours ago
	touch = PortfolioTouchHistory(
		portfolio_id=portfolio.id,
		ticker="AAPL",
		last_decision_timestamp=datetime.now() - timedelta(hours=49),
		last_action="BUY",
	)
	db_session.add(touch)
	db_session.commit()

	decision = {"ticker": "AAPL", "action": "SELL", "quantity": 10}
	now = datetime.now()

	# Should pass — 49 hours > 48 hour cooldown
	allowed, reason = await check_trading_constraints(db_session, portfolio, decision, now)

	assert allowed is True
	assert reason is None


@pytest.mark.asyncio
async def test_constraint_check_frequency_cap_buys(db_session, portfolio):
	"""Should block BUY when portfolio has 5+ buys on same ticker in past week."""
	# Create 5 executed BUY trades in the past 7 days
	for i in range(5):
		trade = Trade(
			portfolio_id=portfolio.id,
			ticker="AAPL",
			action="BUY",
			quantity=10,
			price=150.0,
			executed=True,
			guardrail_passed=True,
			timestamp=datetime.now() - timedelta(days=i),
		)
		db_session.add(trade)
	db_session.commit()

	decision = {"ticker": "AAPL", "action": "BUY", "quantity": 10}
	now = datetime.now()

	# Should fail — already at 5 buys
	allowed, reason = await check_trading_constraints(db_session, portfolio, decision, now)

	assert allowed is False
	assert "Frequency cap" in reason
	assert "max 5 buys" in reason


@pytest.mark.asyncio
async def test_constraint_check_frequency_cap_sells(db_session, portfolio):
	"""Should block SELL when portfolio has 5+ sells on same ticker in past week."""
	# Create 5 executed SELL trades in the past 7 days
	for i in range(5):
		trade = Trade(
			portfolio_id=portfolio.id,
			ticker="MSFT",
			action="SELL",
			quantity=10,
			price=300.0,
			executed=True,
			guardrail_passed=True,
			timestamp=datetime.now() - timedelta(days=i),
		)
		db_session.add(trade)
	db_session.commit()

	decision = {"ticker": "MSFT", "action": "SELL", "quantity": 10}
	now = datetime.now()

	# Should fail — already at 5 sells
	allowed, reason = await check_trading_constraints(db_session, portfolio, decision, now)

	assert allowed is False
	assert "Frequency cap" in reason
	assert "max 5 sells" in reason


@pytest.mark.asyncio
async def test_constraint_check_frequency_allows_under_cap(db_session, portfolio):
	"""Should allow trades when below frequency caps."""
	# Create 3 executed BUY trades
	for i in range(3):
		trade = Trade(
			portfolio_id=portfolio.id,
			ticker="AAPL",
			action="BUY",
			quantity=10,
			price=150.0,
			executed=True,
			guardrail_passed=True,
			timestamp=datetime.now() - timedelta(days=i),
		)
		db_session.add(trade)
	db_session.commit()

	decision = {"ticker": "AAPL", "action": "BUY", "quantity": 10}
	now = datetime.now()

	# Should pass — only 3 buys, under the cap of 5
	allowed, reason = await check_trading_constraints(db_session, portfolio, decision, now)

	assert allowed is True
	assert reason is None


@pytest.mark.asyncio
async def test_constraint_allows_repeat_action(db_session, portfolio):
	"""Repeating the same action on a ticker is allowed — cooldown + frequency cap are the safeguards."""
	touch = PortfolioTouchHistory(
		portfolio_id=portfolio.id,
		ticker="AAPL",
		last_decision_timestamp=datetime.now() - timedelta(hours=50),
		last_action="BUY",
	)
	db_session.add(touch)
	db_session.commit()

	decision = {"ticker": "AAPL", "action": "BUY", "quantity": 10}
	now = datetime.now()

	allowed, reason = await check_trading_constraints(db_session, portfolio, decision, now)

	assert allowed is True
	assert reason is None


@pytest.mark.asyncio
async def test_update_touch_history_creates_new_entry(db_session, portfolio):
	"""update_touch_history should create a new entry if none exists."""
	trade = Trade(
		portfolio_id=portfolio.id,
		ticker="AAPL",
		action="BUY",
		quantity=10,
		price=150.0,
		executed=True,
		guardrail_passed=True,
	)
	db_session.add(trade)
	db_session.commit()

	now = datetime.now()
	await update_touch_history(db_session, portfolio, trade, now)

	touch = db_session.query(PortfolioTouchHistory).filter_by(
		portfolio_id=portfolio.id, ticker="AAPL"
	).first()

	assert touch is not None
	assert touch.last_action == "BUY"
	assert touch.last_decision_timestamp == now


@pytest.mark.asyncio
async def test_update_touch_history_updates_existing_entry(db_session, portfolio):
	"""update_touch_history should update existing entry with new timestamp/action."""
	# Create initial touch history
	touch = PortfolioTouchHistory(
		portfolio_id=portfolio.id,
		ticker="AAPL",
		last_decision_timestamp=datetime.now() - timedelta(hours=10),
		last_action="BUY",
	)
	db_session.add(touch)
	db_session.commit()

	# Create a new trade with SELL action
	trade = Trade(
		portfolio_id=portfolio.id,
		ticker="AAPL",
		action="SELL",
		quantity=10,
		price=160.0,
		executed=True,
		guardrail_passed=True,
	)
	db_session.add(trade)
	db_session.commit()

	now = datetime.now()
	await update_touch_history(db_session, portfolio, trade, now)

	# Verify touch history was updated
	touch = db_session.query(PortfolioTouchHistory).filter_by(
		portfolio_id=portfolio.id, ticker="AAPL"
	).first()

	assert touch is not None
	assert touch.last_action == "SELL"
	assert touch.last_decision_timestamp == now


@pytest.mark.asyncio
async def test_constraints_isolated_per_portfolio(db_session):
	"""Constraints should be portfolio-isolated — trades in one don't affect another."""
	# Create two portfolios
	p1 = Portfolio(
		name="Portfolio 1",
		budget=10000,
		virtual_cash=10000,
		trading_goal="maximize_returns",
		risk_profile="moderate",
		trading_frequency="1x",
	)
	p2 = Portfolio(
		name="Portfolio 2",
		budget=10000,
		virtual_cash=10000,
		trading_goal="maximize_returns",
		risk_profile="moderate",
		trading_frequency="1x",
	)
	db_session.add(p1)
	db_session.add(p2)
	db_session.commit()

	# Create 5 BUY trades in portfolio 1
	for i in range(5):
		trade = Trade(
			portfolio_id=p1.id,
			ticker="AAPL",
			action="BUY",
			quantity=10,
			price=150.0,
			executed=True,
			guardrail_passed=True,
			timestamp=datetime.now() - timedelta(days=i),
		)
		db_session.add(trade)
	db_session.commit()

	# Check constraint on portfolio 2 — should PASS (no trades on p2)
	decision = {"ticker": "AAPL", "action": "BUY", "quantity": 10}
	now = datetime.now()

	allowed, reason = await check_trading_constraints(db_session, p2, decision, now)

	assert allowed is True
	assert reason is None
