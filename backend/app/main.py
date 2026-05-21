"""FastAPI application — route registration and middleware."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.auth import require_auth
from app.config import settings
from app.database import Base, engine
from app.backtest.routes import router as backtest_router
from app.earnings.routes import router as earnings_router
from app.forex.routes import router as forex_router
from app.plans.routes import router as plans_router
from app.screener.routes import router as screener_router
from app.routes import bot, portfolio, todos, trades
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_default_portfolio()
    start_scheduler()
    yield
    stop_scheduler()


def _ensure_default_portfolio() -> None:
    """Create a 'Main' portfolio if none exist.

    Mirrors migration 075 for fresh dev environments where create_all() built
    the schema but the SQL migration didn't run. Idempotent — only inserts
    when the portfolios table is empty.
    """
    from decimal import Decimal
    from app.database import SessionLocal
    from app.plans.models import Portfolio

    db = SessionLocal()
    try:
        if db.query(Portfolio).count() > 0:
            return
        main = Portfolio(
            name="Main",
            budget=Decimal("100000"),
            virtual_cash=Decimal("100000"),
            trading_goal="maximize_returns",
            risk_profile="moderate",
            trading_frequency="1x",
            is_active=True,
        )
        db.add(main)
        db.commit()
        logging.getLogger(__name__).info("Created default 'Main' portfolio (id=%d)", main.id)
    finally:
        db.close()


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# 096-fix: Disable Swagger/OpenAPI docs in production to reduce attack surface
_is_prod = os.getenv("RAILWAY_ENVIRONMENT") == "production"
app = FastAPI(
    title="bahtzang-trader API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    """Add Cache-Control headers to GET responses for read-only endpoints."""
    response = await call_next(request)
    if request.method == "GET" and response.status_code == 200:
        path = request.url.path
        if path == "/health":
            response.headers["Cache-Control"] = "no-cache"
        elif path.startswith("/portfolio/snapshots") or path.startswith("/portfolio/metrics"):
            response.headers["Cache-Control"] = "private, max-age=300"
        elif path.startswith("/trades") and "/export" not in path:
            response.headers["Cache-Control"] = "private, max-age=60"
        elif path.startswith("/earnings"):
            response.headers["Cache-Control"] = "private, max-age=3600"
        elif path.startswith("/backtest"):
            response.headers["Cache-Control"] = "private, max-age=300"
        elif path == "/screener":
            response.headers["Cache-Control"] = "private, max-age=300"
        elif path == "/portfolios":
            response.headers["Cache-Control"] = "private, max-age=60"
        elif path == "/forex/symbols":
            response.headers["Cache-Control"] = "private, max-age=86400"
        elif path == "/forex/backtests":
            response.headers["Cache-Control"] = "private, max-age=60"
        # Skip caching /forex/backtests/{id} — that endpoint is polled while
        # a backtest is running; caching would freeze the status display.
    return response


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Protected — auth check via route-level Depends(require_auth)
# ---------------------------------------------------------------------------


@app.get("/auth/me")
def get_current_user(user: dict = Depends(require_auth)):
    """Return the authenticated user's profile from the Supabase JWT."""
    return user


# Feature module routers
app.include_router(portfolio.router)
app.include_router(trades.router)
app.include_router(bot.router)
app.include_router(todos.router)
app.include_router(backtest_router)
app.include_router(earnings_router)
app.include_router(forex_router)
app.include_router(plans_router)
app.include_router(screener_router)
