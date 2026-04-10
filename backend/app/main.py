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


@app.post("/auth/debug")
def auth_debug(body: dict):
    """TEMPORARY: diagnose JWT verification issues. Remove after debugging."""
    import jwt as pyjwt

    token = body.get("token", "")
    results = {}

    # Step 1: decode without verification to see the payload
    try:
        unverified = pyjwt.decode(token, options={"verify_signature": False})
        results["unverified_payload"] = {
            k: v for k, v in unverified.items()
            if k in ("aud", "role", "email", "iss", "exp", "iat")
        }
    except Exception as e:
        results["unverified_error"] = str(e)

    # Step 2: try with our secret, no audience check
    try:
        pyjwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"],
                      options={"verify_aud": False})
        results["signature_valid"] = True
    except pyjwt.InvalidSignatureError:
        results["signature_valid"] = False
        results["signature_error"] = "Signature mismatch — wrong JWT secret"
    except Exception as e:
        results["signature_error"] = f"{type(e).__name__}: {e}"

    # Step 3: try full verification
    try:
        pyjwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"],
                      audience="authenticated")
        results["full_verify"] = "OK"
    except Exception as e:
        results["full_verify_error"] = f"{type(e).__name__}: {e}"

    results["jwt_secret_length"] = len(settings.SUPABASE_JWT_SECRET)

    return results


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
