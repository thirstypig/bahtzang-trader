"""Pin migration 075's runtime equivalent — _ensure_default_portfolio.

The lifespan hook creates a 'Main' portfolio when the portfolios table is
empty (fresh dev / test env), mirroring what the SQL migration does in prod.
"""

from unittest.mock import patch

from sqlalchemy.orm import sessionmaker

from app.plans.models import Portfolio
from tests.conftest import make_plan


def _patched_session_factory(db_engine):
    """Return a SessionLocal-shaped callable bound to the test engine."""
    return sessionmaker(bind=db_engine)


def test_creates_main_when_table_empty(db_engine, db_session):
    from app.main import _ensure_default_portfolio

    factory = _patched_session_factory(db_engine)
    with patch("app.database.SessionLocal", factory):
        _ensure_default_portfolio()

    portfolios = db_session.query(Portfolio).all()
    assert len(portfolios) == 1
    main = portfolios[0]
    assert main.name == "Main"
    assert main.is_active is True
    assert main.risk_profile == "moderate"
    assert main.trading_goal == "maximize_returns"
    assert main.trading_frequency == "1x"
    assert float(main.budget) == 100000
    assert float(main.virtual_cash) == 100000


def test_idempotent_when_portfolio_exists(db_engine, db_session):
    from app.main import _ensure_default_portfolio

    existing = make_plan(db_session, name="Aggressive Growth", budget=50000)

    factory = _patched_session_factory(db_engine)
    with patch("app.database.SessionLocal", factory):
        _ensure_default_portfolio()

    portfolios = db_session.query(Portfolio).all()
    assert len(portfolios) == 1
    assert portfolios[0].id == existing.id
    assert portfolios[0].name == "Aggressive Growth"
