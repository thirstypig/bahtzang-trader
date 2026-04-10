"""FastAPI application — route registration and middleware."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import require_auth
from app.config import settings
from app.database import Base, engine
from app.routes import bot, guardrails, portfolio, trades
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="bahtzang-trader API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


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
app.include_router(guardrails.router)
app.include_router(bot.router)
