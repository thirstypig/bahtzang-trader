import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.config import settings
from app.database import Base, engine, get_db
from app.guardrails import load_guardrails, save_guardrails
from app.models import Trade
from app.scheduler import start_scheduler, stop_scheduler
from app.trade_executor import run_cycle

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
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Protected — all require valid Supabase JWT
# ---------------------------------------------------------------------------


@app.get("/auth/me")
def get_current_user(user: dict = Depends(require_auth)):
    """Return the authenticated user's profile from the Supabase JWT."""
    return user


@app.get("/portfolio")
async def get_portfolio(user: dict = Depends(require_auth)):
    """Current holdings and cash balance."""
    from app.schwab_client import get_account_balance, get_positions

    account_id = "default"
    positions = await get_positions(account_id)
    balance = await get_account_balance(account_id)
    return {"positions": positions, "balance": balance}


@app.get("/trades")
def get_trades(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Full trade history with decisions and reasoning."""
    trades = (
        db.query(Trade).order_by(Trade.timestamp.desc()).limit(limit).all()
    )
    return [
        {
            "id": t.id,
            "timestamp": t.timestamp.isoformat(),
            "ticker": t.ticker,
            "action": t.action,
            "quantity": t.quantity,
            "price": t.price,
            "claude_reasoning": t.claude_reasoning,
            "confidence": t.confidence,
            "guardrail_passed": t.guardrail_passed,
            "guardrail_block_reason": t.guardrail_block_reason,
            "executed": t.executed,
        }
        for t in trades
    ]


@app.get("/guardrails")
def get_guardrails(user: dict = Depends(require_auth)):
    """Current guardrail settings."""
    return load_guardrails()


@app.post("/guardrails")
def update_guardrails(config: dict, user: dict = Depends(require_auth)):
    """Update guardrail settings."""
    current = load_guardrails()
    current.update(config)
    return save_guardrails(current)


@app.post("/killswitch")
def killswitch(user: dict = Depends(require_auth)):
    """Immediately halt all trading."""
    config = load_guardrails()
    config["kill_switch"] = True
    save_guardrails(config)
    return {"status": "Kill switch activated", "kill_switch": True}


@app.post("/run")
async def manual_run(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Manually trigger one trading cycle."""
    result = await run_cycle(db)
    return result
