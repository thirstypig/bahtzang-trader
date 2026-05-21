"""run_screener orchestration — persistence + status transitions.

rank_universe (pure ranking) is covered in test_engine.py. This covers the IO
orchestrator: it must persist a ScreenerRun + ranked candidates and land on the
right status. The data layer (Alpaca fetch + DB bar load) is mocked at the
boundary so no network is touched.

Concrete regressions guarded:
  - a successful run persists ranked candidates and marks status="complete"
  - a failing data fetch marks status="failed" (not stuck "running") + records error
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import AsyncMock, patch

# Register models before the test DB is built.
from app.models import ScreenerRun, ScreenerCandidate  # noqa: F401
from app.screener.engine import run_screener


def _bars(daily: float, n: int = 260) -> pd.DataFrame:
    closes = 100.0 * np.cumprod(1 + np.full(n, daily))
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": 1_000_000},
        index=idx,
    )


@pytest.mark.integration
class TestRunScreener:
    async def test_persists_ranked_candidates_and_marks_complete(self, db_session):
        bars = {"UP": _bars(0.002), "DOWN": _bars(-0.002), "SPY": _bars(0.0003)}
        with patch("app.backtest.data.fetch_and_cache_bars", new=AsyncMock(return_value=None)), \
             patch("app.backtest.data.load_bars", return_value=bars):
            run = await run_screener(db_session, universe=["UP", "DOWN"], top_n=10)

        assert run.status == "complete"
        assert run.universe_size == 3        # UP, DOWN + SPY benchmark appended
        assert run.scored_count > 0

        cands = (
            db_session.query(ScreenerCandidate)
            .filter(ScreenerCandidate.run_id == run.id)
            .order_by(ScreenerCandidate.rank)
            .all()
        )
        assert cands, "expected persisted candidates"
        assert cands[0].ticker == "UP"        # uptrend ranks above downtrend
        assert cands[0].rank == 1

    async def test_marks_failed_when_data_fetch_raises(self, db_session):
        with patch(
            "app.backtest.data.fetch_and_cache_bars",
            new=AsyncMock(side_effect=RuntimeError("alpaca down")),
        ):
            run = await run_screener(db_session, universe=["UP"], top_n=10)

        assert run.status == "failed"          # not left "running"
        assert "alpaca down" in (run.error or "")
        # No candidates persisted on failure
        assert (
            db_session.query(ScreenerCandidate).filter(ScreenerCandidate.run_id == run.id).count()
            == 0
        )
