"""Shared test fixtures for the bahtzang-trader backend.

Provides:
- SQLite in-memory database (fast, no Postgres needed)
- FastAPI TestClient with auth bypass
- Mock broker that simulates Alpaca without network calls
"""

import os
import sys
from types import ModuleType
from unittest.mock import MagicMock as _MagicMock

# Set required env vars BEFORE any app imports touch pydantic-settings
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("ALPHA_VANTAGE_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("ALLOWED_EMAIL", "test@example.com")
os.environ.setdefault("ALPACA_API_KEY", "test-key")
os.environ.setdefault("ALPACA_SECRET_KEY", "test-secret")

# Stub out heavy native deps that are hard to install in test envs
# (numba, pandas_ta). These are only used by technical_analysis.py
# which we mock in tests anyway.
for mod_name in ("numba", "pandas_ta", "pandas_ta.utils", "pandas_ta.utils._math"):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = _MagicMock()

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.auth import require_auth


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine with all tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # SQLite doesn't enforce FK constraints by default — enable them
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Provide a transactional DB session that rolls back after each test."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

_MOCK_USER = {
    "id": "test-user-id",
    "email": "test@example.com",
    "name": "Test User",
    "picture": "",
}


def _mock_require_auth():
    """Bypass JWT verification for tests."""
    return _MOCK_USER


# ---------------------------------------------------------------------------
# Broker fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_broker():
    """Mock AlpacaBroker that returns sensible defaults without network calls."""
    broker = MagicMock()
    broker.get_positions = AsyncMock(return_value=[])
    broker.get_account_balance = AsyncMock(return_value={
        "cash_available": 100_000.0,
        "total_value": 100_000.0,
    })
    broker.place_order = AsyncMock(return_value={
        "order_id": "mock-order-123",
        "status": "filled",
    })
    return broker


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------

@pytest.fixture
def client(db_engine):
    """TestClient with auth bypassed and DB pointed to SQLite.

    Patches:
    - get_db → test SQLite session
    - require_auth → bypass JWT
    - _validate_budget → skip pg_advisory_xact_lock (SQLite-incompatible)
    - app.database.engine → test engine (for lifespan's create_all)
    """
    from app.main import app

    Session = sessionmaker(bind=db_engine)

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    async def _noop_validate_budget(db, new_budget, exclude_plan_id=None):
        pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_auth] = _mock_require_auth

    # Replace the lifespan to use our test engine and skip scheduler
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def test_lifespan(app):
        Base.metadata.create_all(bind=db_engine)
        yield

    original_router_lifespan = app.router.lifespan_context
    app.router.lifespan_context = test_lifespan

    with patch("app.plans.routes._validate_budget", _noop_validate_budget):
        with TestClient(app) as c:
            yield c

    app.router.lifespan_context = original_router_lifespan

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_plan(db_session, **overrides):
    """Insert a Plan row with sensible defaults. Returns the Plan object."""
    from app.plans.models import Plan

    defaults = {
        "name": "Test Plan",
        "budget": 5000.0,
        "virtual_cash": 5000.0,
        "trading_goal": "maximize_returns",
        "risk_profile": "moderate",
        "trading_frequency": "1x",
        "is_active": True,
    }
    defaults.update(overrides)
    plan = Plan(**defaults)
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


def make_trade(db_session, plan_id, **overrides):
    """Insert a Trade row for a plan with sensible defaults.

    067-fix: Uses unified Trade table with plan_id instead of PlanTrade.
    """
    from app.models import Trade

    defaults = {
        "plan_id": plan_id,
        "ticker": "AAPL",
        "action": "buy",
        "quantity": 1.0,
        "price": 150.0,
        "guardrail_passed": True,
        "executed": True,
        "virtual_cash_before": 5000.0,
        "virtual_cash_after": 4850.0,
    }
    defaults.update(overrides)
    trade = Trade(**defaults)
    db_session.add(trade)
    db_session.commit()
    db_session.refresh(trade)
    return trade
