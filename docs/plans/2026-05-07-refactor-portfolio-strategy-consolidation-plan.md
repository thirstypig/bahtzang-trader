---
id: DOC-034
type: plan
status: done
phase: null
owner: james
tags: [portfolios, backend]
links: []
updated: 2026-05-07
legacy_type: refactor
---

# Consolidate Settings + Plans → Unified Portfolio System

## Overview

Merge two separate concepts (Settings and Plans) into a single **Portfolio** system where each portfolio encapsulates allocation, strategy rules, and position history. Enables per-portfolio rule customization, prevents repetitive trading via cooldown/frequency enforcement, and establishes a clear mental model: **one portfolio = one strategy + one allocation**.

**Strategic importance:** This consolidation locks in the Portfolio concept for Phase G live-trading graduation and beyond (crypto/forex expansion in Phase G+).

## Problem Statement

**Current architecture:**
- Settings: Product-wide guardrails stored in singleton table (`guardrails_config`, id=1)
- Plans: Virtual sub-accounts with budgets and trading goals, but no per-plan trading rules
- Result: Ambiguity about scope (are guardrails global or per-plan?) and inability to have different rules per portfolio

**Pain points:**
1. "Settings" is too vague — unclear whether they apply globally or per-portfolio
2. "Plans" don't capture strategy — only allocation and goal, no explicit trading discipline
3. No per-ticker cooldown prevents repetitive whipsaw trading (buy AAPL, sell, buy again 1 hour later)
4. No frequency limits enforce diversification (could trade same 5 tickers every day)
5. Strategy changes not tracked — unclear when rules changed or why a trade was blocked

**Enabling constraints solved by consolidation:**
- Per-portfolio cooldown rules (24h default, user-configurable on creation)
- Trading frequency caps (max 5 buys + 5 sells per ticker per week)
- No duplicate action per ticker (can't buy AAPL twice in a row)
- Audit log for rule changes with timestamp and user
- Existing positions preserved when rules change (new rules apply prospectively)

## Proposed Solution

### Architecture: Before → After

**Before:**
```
Settings (global singleton)
├── Risk profile (one choice for whole app)
├── Trading goal (one choice for whole app)
├── Frequency limit (global)
└── All other guardrails

Plans (per-account slices)
├── Name & budget
├── Trading goal
├── Risk profile
└── (no explicit rules beyond inherited Settings)
```

**After:**
```
Portfolio (one unified concept, many instances)
├── Name & budget
├── Strategy (explicit rules)
│   ├── Confidence threshold
│   ├── Per-ticker cooldown (24–48 hrs, user-set at creation)
│   ├── Max 5 buys + 5 sells per ticker per week
│   ├── No same action twice per ticker
│   ├── Risk profile (conservative/moderate/aggressive)
│   └── Trading goal (6 preset options)
├── Position tracking
│   ├── Virtual positions (aggregate buys/sells)
│   ├── Touch history (last trade time per ticker)
│   └── Action history (last action per ticker)
└── Audit log (rule changes with timestamp)
```

### Key Architectural Decisions (from brainstorm — see docs/brainstorms/2026-05-07-portfolio-strategy-consolidation-brainstorm.md)

| Decision | Rationale | Locked? |
|----------|-----------|---------|
| Decision time, not execution time for cooldown | More accurate to when signal fired, not when Alpaca filled | ✓ Yes |
| Max 5 buys + 5 sells per ticker per week (10 total) | Allows active rebalancing while still preventing daily churn | ✓ Yes |
| User chooses cooldown on portfolio creation | Maximize flexibility; let users pick conservative/balanced/aggressive | ✓ Yes |
| Existing positions preserved when rules change | Don't force-close positions Claude already made; new rules apply prospectively | ✓ Yes |
| Rule changes logged in audit trail | Show user WHEN rules changed to correlate with trade performance | ✓ Yes |

### UI/Route Changes

| Current | New | Status |
|---------|-----|--------|
| `/settings` | ❌ Remove entirely | Eliminate product-wide settings page |
| `/plans` | ✅ `/portfolios` | Rename route |
| `/plans/new` | ✅ `/portfolios/new` | Update route |
| `/plans/[id]` | ✅ `/portfolios/[id]` | Update route (add Strategy tab) |
| `/plans/[id]/rules` | ✨ **NEW** | Strategy rules configuration per portfolio |

Inside each portfolio:
- Allocation tab: Budget, trading goal, target P&L
- **Strategy tab (new):** Cooldown hours, confidence threshold, frequency caps
- Positions tab: Current holdings, touch history
- **Audit log tab (new):** Rule change history with timestamps

## Technical Approach

### Phase 1: Database Schema & Models

**Migrations needed:**

1. **Rename Plans table → Portfolios**
   ```sql
   ALTER TABLE plans RENAME TO portfolios;
   ALTER TABLE plan_snapshots RENAME TO portfolio_snapshots;
   ALTER INDEX ix_plan_snapshots_plan_date RENAME TO ix_portfolio_snapshots_portfolio_date;
   ALTER TABLE plan_snapshots RENAME CONSTRAINT fk_plan_snapshots_plan_id TO fk_portfolio_snapshots_portfolio_id;
   ALTER TABLE trades RENAME COLUMN plan_id TO portfolio_id;
   ALTER INDEX ix_trades_plan_timestamp RENAME TO ix_trades_portfolio_timestamp;
   -- Update all other references...
   ```

2. **Add strategy columns to portfolios table**
   ```sql
   ALTER TABLE portfolios ADD COLUMN (
     cooldown_hours INTEGER NOT NULL DEFAULT 48,
     min_confidence NUMERIC(5,2) NOT NULL DEFAULT 0.55,
     respect_wash_sale BOOLEAN NOT NULL DEFAULT TRUE,
     kelly_fraction NUMERIC(3,2) NOT NULL DEFAULT 0.15,
     circuit_breaker_daily_pct NUMERIC(5,2) NOT NULL DEFAULT -5.0,
     circuit_breaker_weekly_pct NUMERIC(5,2) NOT NULL DEFAULT -10.0
   );
   ```

3. **New: portfolio_touch_history table** (tracks last trade time per ticker)
   ```sql
   CREATE TABLE portfolio_touch_history (
     id BIGSERIAL PRIMARY KEY,
     portfolio_id BIGINT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
     ticker VARCHAR(10) NOT NULL,
     last_decision_timestamp TIMESTAMP NOT NULL,
     last_action VARCHAR(10) NOT NULL,
     created_at TIMESTAMP DEFAULT NOW(),
     updated_at TIMESTAMP DEFAULT NOW(),
     UNIQUE(portfolio_id, ticker),
     INDEX ix_portfolio_touch_history_portfolio_ticker (portfolio_id, ticker)
   );
   ```

4. **New: portfolio_strategy_audit table** (rule change log)
   ```sql
   CREATE TABLE portfolio_strategy_audit (
     id BIGSERIAL PRIMARY KEY,
     portfolio_id BIGINT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
     user_email VARCHAR(255) NOT NULL,
     timestamp TIMESTAMP DEFAULT NOW(),
     action VARCHAR(50) NOT NULL, -- 'cooldown_changed', 'confidence_updated', etc.
     old_value TEXT,
     new_value TEXT,
     reason TEXT,
     INDEX ix_portfolio_strategy_audit_portfolio_timestamp (portfolio_id, timestamp DESC)
   );
   ```

5. **Remove guardrails_config table** (no longer needed at global scope)
   - Guardrails become per-portfolio instead of global

**Model updates (Python):**

```python
# backend/app/models.py

class Portfolio(Base):
    __tablename__ = "portfolios"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    budget: Mapped[Decimal] = mapped_column(Numeric(14,4))
    virtual_cash: Mapped[Decimal] = mapped_column(Numeric(14,4))
    
    # Strategy rules (formerly in GuardrailsConfig, now per-portfolio)
    cooldown_hours: Mapped[int] = mapped_column(default=48)
    min_confidence: Mapped[Decimal] = mapped_column(Numeric(5,2), default=Decimal("0.55"))
    respect_wash_sale: Mapped[bool] = mapped_column(default=True)
    kelly_fraction: Mapped[Decimal] = mapped_column(Numeric(3,2), default=Decimal("0.15"))
    circuit_breaker_daily_pct: Mapped[Decimal] = mapped_column(Numeric(5,2), default=Decimal("-5.0"))
    circuit_breaker_weekly_pct: Mapped[Decimal] = mapped_column(Numeric(5,2), default=Decimal("-10.0"))
    
    # Legacy allocation fields
    trading_goal: Mapped[str]
    risk_profile: Mapped[str]
    trading_frequency: Mapped[str]
    target_amount: Mapped[Optional[Decimal]]
    target_date: Mapped[Optional[date]]
    is_active: Mapped[bool] = mapped_column(default=True)
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    trades: Mapped[List["Trade"]] = relationship("Trade", back_populates="portfolio")
    snapshots: Mapped[List["PortfolioSnapshot"]] = relationship("PortfolioSnapshot", back_populates="portfolio", cascade="all, delete-orphan")
    touch_history: Mapped[List["PortfolioTouchHistory"]] = relationship("PortfolioTouchHistory", cascade="all, delete-orphan")
    strategy_audit: Mapped[List["PortfolioStrategyAudit"]] = relationship("PortfolioStrategyAudit", cascade="all, delete-orphan")

class PortfolioTouchHistory(Base):
    __tablename__ = "portfolio_touch_history"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"))
    ticker: Mapped[str] = mapped_column(String(10))
    last_decision_timestamp: Mapped[datetime]
    last_action: Mapped[str]  # 'BUY', 'SELL', 'HOLD'
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('portfolio_id', 'ticker', name='uq_portfolio_ticker'),
        Index('ix_portfolio_touch_history_portfolio_ticker', 'portfolio_id', 'ticker'),
    )

class PortfolioStrategyAudit(Base):
    __tablename__ = "portfolio_strategy_audit"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"))
    user_email: Mapped[str] = mapped_column(String(255))
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    action: Mapped[str]  # 'cooldown_changed', 'confidence_updated', etc.
    old_value: Mapped[Optional[str]]
    new_value: Mapped[Optional[str]]
    reason: Mapped[Optional[str]]
    
    __table_args__ = (
        Index('ix_portfolio_strategy_audit_portfolio_timestamp', 'portfolio_id', desc('timestamp')),
    )
```

### Phase 2: Backend API Routes

**Rename and refactor endpoints:**

```python
# backend/app/routes/portfolios.py (renamed from plans.py)

@router.get("/portfolios")
async def list_portfolios(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """List all portfolios with current strategy summary."""
    # Response includes new fields: cooldown_hours, min_confidence, etc.

@router.post("/portfolios")
async def create_portfolio(
    req: PortfolioCreateRequest,  # New: includes cooldown_hours, min_confidence
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Create portfolio. User chooses cooldown on creation."""
    # Validate budget
    # Create portfolio with strategy rules
    # Log audit entry

@router.patch("/portfolios/{portfolio_id}")
async def update_portfolio(
    portfolio_id: int,
    req: PortfolioUpdateRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Update portfolio allocation AND/OR strategy rules.
    
    If strategy rules change:
    - Log all changes to portfolio_strategy_audit
    - Existing positions unaffected
    - New rules apply to future decisions
    """
    # If cooldown/confidence/etc. changed:
    #   → log to portfolio_strategy_audit with user_email, timestamp
    #   → do NOT reset touch_history for existing positions
    # Existing positions stay; new rules apply prospectively

@router.get("/portfolios/{portfolio_id}/strategy")
async def get_portfolio_strategy(
    portfolio_id: int,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Get portfolio's current strategy rules + audit log."""
    # Return current cooldown, confidence, frequency caps
    # Return audit log with 50 most recent changes

@router.post("/portfolios/{portfolio_id}/strategy")
async def update_portfolio_strategy(
    portfolio_id: int,
    req: StrategyUpdateRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Update strategy rules for portfolio."""
    # Log to portfolio_strategy_audit
    # Audit entry includes: old value, new value, user email, timestamp, reason
```

**Remove guardrails endpoints:**
- ❌ `GET /guardrails` (product-wide settings)
- ❌ `POST /guardrails` (product-wide updates)
- ✅ Replaced by per-portfolio `/portfolios/{id}/strategy` endpoints

**New request/response types:**

```python
class PortfolioCreateRequest(BaseModel):
    name: str
    budget: Decimal  # in dollars
    trading_goal: str  # must be one of 6 preset goals
    risk_profile: str  # conservative|moderate|aggressive
    trading_frequency: str  # 1x|3x|5x
    cooldown_hours: int  # user chooses: 24, 48, etc. (validated 1-168)
    min_confidence: Decimal = Decimal("0.55")  # optional override
    target_amount: Optional[Decimal] = None
    target_date: Optional[date] = None

class StrategyUpdateRequest(BaseModel):
    cooldown_hours: Optional[int] = None
    min_confidence: Optional[Decimal] = None
    respect_wash_sale: Optional[bool] = None
    kelly_fraction: Optional[Decimal] = None
    circuit_breaker_daily_pct: Optional[Decimal] = None
    circuit_breaker_weekly_pct: Optional[Decimal] = None
    reason: Optional[str] = None  # user notes why rules changed
```

### Phase 3: Frontend Routes & Components

**Route migration:**

| Old | New | Component Changes |
|-----|-----|-------------------|
| `/settings` | ❌ Remove | Delete app/settings/page.tsx |
| `/plans` | `/portfolios` | Rename page.tsx, update imports |
| `/plans/new` | `/portfolios/new` | Rename + update form (add cooldown picker) |
| `/plans/[id]` | `/portfolios/[id]` | Rename + restructure tabs |

**New component: PortfolioStrategyForm**

```typescript
// frontend/src/components/PortfolioStrategyForm.tsx

export default function PortfolioStrategyForm({ portfolio }: { portfolio: Portfolio }) {
  // Cooldown picker: radio buttons or dropdown for 24h / 48h / custom hours
  // Confidence threshold slider
  // Frequency cap display (5 buys + 5 sells per week)
  // Audit log: show last 20 rule changes with timestamps
  
  return (
    <div>
      <h3>Strategy Rules</h3>
      <label>
        Per-Ticker Cooldown
        <select value={cooldownHours}>
          <option value={24}>24 hours (Aggressive)</option>
          <option value={48}>48 hours (Balanced)</option>
          <option value={72}>72 hours (Conservative)</option>
          <option value="custom">Custom</option>
        </select>
      </label>
      
      <label>
        Minimum Confidence
        <input type="range" min={0.5} max={0.9} step={0.05} />
      </label>
      
      <fieldset disabled>
        <legend>Frequency Limits (Read-Only)</legend>
        <p>Max 5 buys + 5 sells per ticker per week</p>
        <p>No same action twice in a row per ticker</p>
      </fieldset>
      
      <section>
        <h4>Rule Changes (Audit Log)</h4>
        {auditLog.map(entry => (
          <div key={entry.id}>
            <time>{formatDateTime(entry.timestamp)}</time>
            <strong>{entry.action}</strong>
            <span>{entry.old_value} → {entry.new_value}</span>
            <p>{entry.reason}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
```

**Portfolio detail page structure:**

```
/portfolios/[id]
├── Tabs:
│   ├── Overview (name, budget, equity curve)
│   ├── Allocation (trading goal, target P&L, risk profile)
│   ├── **Strategy (NEW)** (cooldown, confidence, frequency caps, audit log)
│   ├── Positions (holdings, touch history)
│   ├── Trades (trade history for this portfolio)
│   └── Snapshots (daily P&L)
└── Actions: Edit, Run Cycle, Export CSV, Delete
```

### Phase 4: Trading Logic — Cooldown & Frequency Enforcement

**New validation in trade_executor.py / plans/executor.py:**

```python
async def check_trading_constraints(
    db: Session,
    portfolio: Portfolio,
    decision: TradeDecision,
    executor_context: dict
) -> Tuple[bool, Optional[str]]:
    """Check trading frequency rules before executing trade.
    
    Returns: (allowed, reason_if_blocked)
    """
    
    # 1. Check per-ticker cooldown
    touch = db.query(PortfolioTouchHistory).filter_by(
        portfolio_id=portfolio.id,
        ticker=decision.ticker
    ).first()
    
    if touch:
        hours_elapsed = (decision.decision_timestamp - touch.last_decision_timestamp).total_seconds() / 3600
        if hours_elapsed < portfolio.cooldown_hours:
            return False, f"Cooldown: {decision.ticker} touched {hours_elapsed:.1f}h ago, need {portfolio.cooldown_hours}h"
    
    # 2. Check per-ticker frequency (5 buys + 5 sells per week)
    week_start = decision.decision_timestamp - timedelta(days=7)
    buys_this_week = db.query(Trade).filter(
        Trade.portfolio_id == portfolio.id,
        Trade.ticker == decision.ticker,
        Trade.action == "BUY",
        Trade.timestamp >= week_start
    ).count()
    
    sells_this_week = db.query(Trade).filter(
        Trade.portfolio_id == portfolio.id,
        Trade.ticker == decision.ticker,
        Trade.action == "SELL",
        Trade.timestamp >= week_start
    ).count()
    
    if decision.action == "BUY" and buys_this_week >= 5:
        return False, f"Frequency cap: {decision.ticker} max 5 buys/week, already at 5"
    
    if decision.action == "SELL" and sells_this_week >= 5:
        return False, f"Frequency cap: {decision.ticker} max 5 sells/week, already at 5"
    
    # 3. Check no same action twice in a row
    if touch and touch.last_action.upper() == decision.action.upper():
        return False, f"No repeats: {decision.ticker} last action was {touch.last_action}, can't repeat"
    
    return True, None


async def update_touch_history(
    db: Session,
    portfolio: Portfolio,
    trade: Trade,
    decision_timestamp: datetime
):
    """Update last trade time and action for ticker."""
    touch, _ = db.query(PortfolioTouchHistory).get_or_create(
        portfolio_id=portfolio.id,
        ticker=trade.ticker,
        defaults={
            'last_decision_timestamp': decision_timestamp,
            'last_action': trade.action
        }
    )
    touch.last_decision_timestamp = decision_timestamp
    touch.last_action = trade.action
    touch.updated_at = datetime.utcnow()
    db.commit()
```

**Integration with executor:**

```python
# In plans/executor.py: run_plan_cycle()

# ... gather, earnings, think, coerce ...

# NEW: Check trading constraints before validation
allowed, reason = await check_trading_constraints(
    db, portfolio, decision, context
)
if not allowed:
    decision.action = "HOLD"
    decision.reason = reason
    # Still log the blocked decision

# ... continue with existing validation ...

# If trade executes:
if trade.executed:
    await update_touch_history(db, portfolio, trade, decision_timestamp)
    
    # Log rule application to PortfolioStrategyAudit?
    # (No — audit log is only for rule CHANGES, not rule application)
```

### Phase 5: Data Migration & Backward Compatibility

**One-time data migration:**

```python
# scripts/migrate_plans_to_portfolios.py

def migrate_plans_to_portfolios(db: Session):
    """
    Rename tables, backfill strategy rules from guardrails config.
    
    1. Create new tables (touch_history, strategy_audit)
    2. Copy GuardrailsConfig → Portfolio.strategy fields
    3. Update all ForeignKey references (plan_id → portfolio_id)
    4. Create initial PortfolioStrategyAudit entry for each portfolio
    5. Drop old tables/columns
    """
    
    # Step 1: Get current global guardrails (used as baseline for all portfolios)
    guardrails = db.query(GuardrailsConfig).filter_by(id=1).first()
    
    # Step 2: Update all existing plans with strategy rules
    for portfolio in db.query(Portfolio).all():
        portfolio.cooldown_hours = 48  # Default: balanced
        portfolio.min_confidence = guardrails.min_confidence
        portfolio.respect_wash_sale = guardrails.respect_wash_sale
        portfolio.kelly_fraction = guardrails.kelly_fraction
        # ... copy all strategy fields ...
        
        # Step 3: Log initial migration audit entry
        audit = PortfolioStrategyAudit(
            portfolio_id=portfolio.id,
            user_email="system@bahtzang.com",
            timestamp=datetime.utcnow(),
            action="migration_init",
            old_value="guardrails_config (global)",
            new_value="portfolio.strategy fields",
            reason="Migrate from product-wide Settings to per-portfolio Strategy"
        )
        db.add(audit)
    
    db.commit()
```

**Backward compatibility:**
- Old `plan_id` column in trades table renamed to `portfolio_id` (transparent to app)
- Old guarndrails endpoints return 404 (removed)
- New `/portfolios` endpoints accept same request format as old `/plans` (mostly)

### Phase 6: Testing & QA

**New unit tests:**

- ✅ `test_portfolio_cooldown_enforcement` — can't touch ticker within cooldown window
- ✅ `test_portfolio_frequency_cap` — max 5 buys + 5 sells per ticker per week
- ✅ `test_no_same_action_twice` — can't buy AAPL then buy AAPL again
- ✅ `test_strategy_audit_logging` — rule changes logged with timestamp, user, old/new values
- ✅ `test_existing_positions_on_rule_change` — positions NOT closed when rules change
- ✅ `test_touch_history_persistence` — touch history survives rule updates
- ✅ `test_portfolio_migration` — data correctly migrated from plan_id to portfolio_id

**Integration tests:**

- ✅ `test_create_portfolio_with_custom_cooldown` — user picks cooldown on creation
- ✅ `test_update_portfolio_strategy_audit_trail` — audit log tracks all changes
- ✅ `test_trade_blocked_by_cooldown_in_executor` — trading cycle respects cooldown
- ✅ `test_trade_blocked_by_frequency_cap` — trading cycle respects frequency limit
- ✅ `test_paper_trading_respects_all_constraints` — full cycle with all rules enforced

**Manual QA:**

- ✅ Create 3 portfolios with different cooldowns (24h, 48h, custom)
- ✅ Trade same ticker, verify cooldown blocks retouching
- ✅ Try to trade 6th time per week, verify block
- ✅ Try to buy AAPL twice in a row, verify block
- ✅ Change cooldown from 48h to 24h, verify:
  - Old positions NOT closed
  - New rules apply to next trade
  - Audit log shows change with timestamp
- ✅ Verify `/settings` route returns 404
- ✅ Verify `/portfolios` has Strategy tab with audit log

## System-Wide Impact

### Interaction Graph

**Trade decision flow (new cooldown + frequency checks):**

1. **User or scheduler triggers** `POST /portfolios/{id}/run`
2. **Executor calls** `plans/executor.py:run_plan_cycle()`
   - Gathers Alpaca positions + earnings + market data
   - Calls Claude for decision
   - **NEW:** Calls `check_trading_constraints()` before validation
     - Queries `portfolio_touch_history` for cooldown check
     - Queries `trades` table for weekly frequency count
     - Checks `last_action` against current `decision.action`
   - If any constraint fails → coerce action to HOLD with reason
   - Applies existing guardrails (confidence, kill switch, position limits)
   - If trade passes all gates → calls Alpaca API
3. **On successful execution:**
   - **NEW:** Calls `update_touch_history()` to record decision timestamp + action
   - Logs trade to `trades` table with `portfolio_id`
   - Creates `portfolio_snapshot` at 4:05 PM ET
4. **On strategy rule change:**
   - **NEW:** Calls `log_strategy_change()` to audit table
   - Does NOT reset touch history (existing positions live under new rules)
   - New rules apply to next trading cycle

### Error Propagation

**New failure points:**
- ❌ Cooldown check fails → trade coerced to HOLD (non-fatal, logged)
- ❌ Frequency cap hit → trade coerced to HOLD (non-fatal, logged)
- ❌ Same action twice → trade coerced to HOLD (non-fatal, logged)
- ❌ `update_touch_history()` fails → trade still executed but touch history stale (impacts next cycle's cooldown check)
  - Mitigation: Wrap in try-except, log error, don't block trade

**Existing error paths preserved:**
- Confidence below threshold → coerce to HOLD
- Kill switch active → block trade
- Position limit exceeded → coerce to SELL or block
- Alpaca order fails → non-fatal, log error

### State Lifecycle Risks

**Atomicity:**
- Trade execution → touch history update must be atomic (same transaction)
  - If `update_touch_history()` fails after trade executes, next cycle's cooldown check will be wrong
  - Mitigation: Wrap in transaction, retry on failure

**Touch history consistency:**
- If user manually changes portfolio settings, touch history is NOT reset
  - This is intentional: old trades count toward new rules (conservative approach)
  - Audit log makes this transparent

**Cascading deletes:**
- Delete portfolio → cascades delete trades, snapshots, touch_history, strategy_audit
- Delete trade (if allowed) → does NOT delete corresponding touch_history entry
  - Rationale: touch_history reflects real trading history, not just valid trades

### API Surface Parity

**Endpoints that need updating:**
- ✅ `GET /portfolios` (replaces `/plans`)
- ✅ `POST /portfolios` (replaces `/plans`, adds cooldown parameter)
- ✅ `PATCH /portfolios/{id}` (replaces `/plans/{id}`, handles strategy rules)
- ✅ `GET /portfolios/{id}/positions` (same as `/plans/{id}/positions`)
- ✅ `GET /portfolios/{id}/snapshots` (same as `/plans/{id}/snapshots`)
- ✅ `POST /portfolios/{id}/run` (replaces `/plans/{id}/run`)
- ✅ `POST /portfolios/{id}/export` (replaces `/plans/{id}/export`)
- ✨ **NEW:** `GET /portfolios/{id}/strategy` (audit log + current rules)
- ✨ **NEW:** `POST /portfolios/{id}/strategy` (update rules with audit logging)
- ❌ `GET /guardrails` (removed — no global settings)
- ❌ `POST /guardrails` (removed — per-portfolio only)
- ❌ `GET /guardrails/presets` (moved into `/portfolios` endpoints)

**Frontend API calls that need updating:**
- All `getPlans()` → `getPortfolios()`
- All `getPlan()` → `getPortfolio()`
- All `updatePlan()` → `updatePortfolio()`
- All `runPlan()` → `runPortfolio()`
- All `getGuardrails()` and `updateGuardrails()` → `getPortfolioStrategy()` and `updatePortfolioStrategy()`

### Integration Test Scenarios

1. **Create portfolio with custom cooldown:**
   - Create portfolio with 24h cooldown
   - Trade ticker AAPL at 10 AM
   - Try to trade AAPL at 11 AM → blocked with "cooldown not met"
   - Try at 11 AM next day → allowed
   - **Verify:** Correct cooldown window enforced

2. **Frequency cap prevents churn:**
   - Trade same ticker 5 times in one week
   - Try to trade it 6th time → blocked with "frequency cap"
   - Next week → counter resets, allowed again
   - **Verify:** Per-week rolling window works correctly

3. **Rule change doesn't close positions:**
   - Portfolio A has 48h cooldown, owns AAPL, touched it 2 hours ago
   - Change cooldown to 24h
   - AAPL position stays (not sold)
   - Next trading cycle can't touch AAPL for another 46 hours (from original touch time)
   - **Verify:** Touch history NOT reset, position preserved

4. **Audit log tracks rule changes:**
   - Create portfolio, note initial rules in audit log
   - Change cooldown from 48h to 24h
   - Audit log shows: user email, timestamp, old value (48), new value (24)
   - UI displays audit log with last 20 changes
   - **Verify:** Audit trail is complete and navigable

5. **No same action twice:**
   - Buy AAPL at 10 AM
   - Try to buy AAPL again at 10:30 AM → blocked
   - Sell AAPL at 11 AM → allowed (different action)
   - Try to sell AAPL again at 11:30 AM → blocked
   - **Verify:** Action sequence enforced per ticker

## Alternative Approaches Considered

### Alternative A: Keep Settings global, add per-plan overrides
- **Pros:** Backward compatible, less migration effort
- **Cons:** Still ambiguous whether rules are global or per-plan; forces defaults-and-overrides pattern which is confusing
- **Rejected:** Mental model stays muddled; doesn't solve core problem

### Alternative B: Create new "Strategy" table, leave Plans unchanged
- **Pros:** Smaller scope, existing Plan endpoints mostly work
- **Cons:** Adds complexity (join table); Settings + Plans + Strategy = 3 concepts still
- **Rejected:** Doesn't consolidate the core ambiguity

### Alternative C: Consolidate into Portfolio, but keep global guardrails as fallback
- **Pros:** Preserves some global defaults for new portfolios
- **Cons:** Reintroduces the global vs per-portfolio ambiguity; confusing precedence rules
- **Rejected:** Defeats the purpose of consolidation

**Chosen approach (Portfolio = allocation + strategy)** wins because:
- Single clear concept (one portfolio = one allocation + one strategy)
- Enables per-portfolio customization without ambient global rules
- Audit trail shows when rules changed (transparency)
- Scalable to Phase G+ (different rules for different asset classes)

## Risk Analysis & Mitigation

### Risk: Data corruption during migration

**Scenario:** Migration script partially fails; some portfolios get strategy rules, others don't.

**Likelihood:** Low (migration is transactional)

**Impact:** High (inconsistent state)

**Mitigation:**
- Run migration in transaction; rollback on any error
- Test migration against production data copy first
- Verify all portfolios have strategy rules after migration
- Audit log created for every portfolio as proof

---

### Risk: Existing trades no longer have strategy context

**Scenario:** User changes cooldown from 48h to 24h; old trades still "count" under old rule.

**Likelihood:** Medium (expected behavior based on brainstorm decision)

**Impact:** Medium (user confusion if not explained)

**Mitigation:**
- Audit log clearly documents the rule change with timestamp
- UI shows "Strategy rules changed at X; new rules apply to decisions after this timestamp"
- Existing position's touch history shows original touch time (not reset)
- Help docs explain: "Changing rules applies only to future decisions; existing positions live under new rules from now on"

---

### Risk: Cooldown check query is slow on large trade tables

**Scenario:** Portfolio with 10k+ trades; touch history query slow on every cycle.

**Likelihood:** Low (touch_history table is small, indexed)

**Impact:** Medium (trading cycle delayed)

**Mitigation:**
- `portfolio_touch_history` table is sparse (one row per ticker per portfolio, not per trade)
- Indexed on (portfolio_id, ticker) for fast lookups
- Weekly frequency check queries `trades` with indexes on (portfolio_id, ticker, timestamp)
- Monitor query performance; add indexes if needed

---

### Risk: Frequency cap counted wrong (includes old vs new weeks)

**Scenario:** User trades ticker 3 times Monday, 2 times next Monday = 5 total, but different weeks.

**Likelihood:** Low (rolling window query is clear)

**Impact:** Medium (user thinks they're at cap when they're not)

**Mitigation:**
- Frequency check uses `week_start = decision_timestamp - timedelta(days=7)` (rolling 7-day window)
- Test covers this scenario explicitly
- UI could show "X buys + Y sells in last 7 days" for clarity

---

### Risk: Audit log grows unbounded

**Scenario:** User changes cooldown 100 times; audit table bloats.

**Likelihood:** Very low (users change rules rarely)

**Impact:** Low (audit table has retention policy option)

**Mitigation:**
- No cleanup needed for now (audit log is valuable history)
- If needed later: add retention policy (keep last 1 year)
- Index on (portfolio_id, timestamp DESC) enables efficient queries

## Resource Requirements

### Engineering Time

| Phase | Task | Est. Hours | Notes |
|-------|------|-----------|-------|
| **1** | DB schema (migrations + models) | 4 | Table renames, new columns, new tables |
| **2** | Backend API (routes + validation) | 6 | Refactor endpoints, add strategy logic |
| **3** | Frontend (routes + components) | 5 | Rename routes, add Strategy tab + audit UI |
| **4** | Trading logic (cooldown/frequency) | 4 | New validation functions + integration |
| **5** | Data migration + testing | 3 | Backfill, verify, test script |
| **6** | Manual QA + docs | 4 | Full testing scenario, user docs |
| **Contingency** | Buffer (20%) | 5 | |
| **TOTAL** | | ~31 hours | ~4 days at 8h/day, or 1 week at 5h/day |

### Database

- ✅ New tables: `portfolio_touch_history`, `portfolio_strategy_audit`
- ✅ New columns on `portfolios`: cooldown_hours, min_confidence, etc.
- ✅ Indexes: (portfolio_id, ticker), (portfolio_id, timestamp)
- ✅ Migration script (one-time)

### Breaking Changes

- ⚠️ **`/settings` route removed** — users who bookmarked will hit 404
  - Mitigation: Redirect `/settings` → `/portfolios` in Next.js (temporary)
- ⚠️ **`/plans` → `/portfolios` rename** — links in docs/changelog need updating
  - Mitigation: Search-and-replace in docs, old links automatically redirect

## Future Considerations

### Phase G+ Multi-Asset Support

Once this consolidation is complete, adding crypto/forex becomes straightforward:

```python
class Portfolio:
    asset_class: str  # "equities" (default), "crypto", "forex"
    cooldown_hours: int
    
    # Can be extended per-asset:
    # cooldown_crypto_hours, cooldown_forex_hours
```

Portfolios can be:
- All-equities (current)
- Mixed (future) with per-asset-class cooldowns
- All-crypto or all-forex sandboxes

### Extensibility for Advanced Rules

The `PortfolioStrategyAudit` pattern makes it easy to add rule types:
- `max_sector_weight` — can't have >20% in tech
- `min_position_duration` — must hold for N days before selling
- `correlated_ticker_distance` — can't own highly-correlated pairs

Each new rule is just a new audit action type + a check in `check_trading_constraints()`.

## Documentation Plan

- ✅ Update `CLAUDE.md` with new `/portfolios` routes
- ✅ Update `/docs/concepts` to explain Portfolio = allocation + strategy
- ✅ Add help section: "Why did my trade get blocked? (Cooldown, frequency cap, no repeats)"
- ✅ Update changelog with consolidation milestone
- ✅ User docs: "Creating a portfolio" with cooldown picker walkthrough

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-05-07-portfolio-strategy-consolidation-brainstorm.md](docs/brainstorms/2026-05-07-portfolio-strategy-consolidation-brainstorm.md)
  - Key decisions carried forward: Per-ticker cooldown (not global), user chooses cooldown on creation, frequency cap is 5 buys + 5 sells per week, existing positions preserved on rule change

### Internal References

- **Plan model:** `backend/app/plans/models.py:20-60`
- **Plan executor:** `backend/app/plans/executor.py:1-100`
- **Plan routes:** `backend/app/plans/routes.py:33-463`
- **Guardrails model:** `backend/app/models.py:128-167`
- **Guardrails routes:** `backend/app/routes/guardrails.py:28-110`
- **Frontend plans page:** `frontend/src/app/plans/page.tsx`
- **Frontend plan detail:** `frontend/src/app/plans/[id]/page.tsx`
- **Frontend settings page:** `frontend/src/app/settings/page.tsx` (to be removed)
- **Trade model:** `backend/app/models.py:27-95`
- **Decision coercion:** `backend/app/decision_coercion.py` (existing pattern for coercing qty/price to HOLD)

### External References

- SQLAlchemy 2.0 Mapped types: https://docs.sqlalchemy.org/en/20/orm/mapped_attributes.html
- PostgreSQL advisory locks: https://www.postgresql.org/docs/current/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS
- Async transaction management: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

### Related Work

- **Migration 067:** Unified Trade + PlanTrade tables
- **Migration 071:** Converted FLOAT → NUMERIC(14,4) for precise money arithmetic
- **Migration 082:** Added advisory lock pattern for budget validation
- **Fix 076:** CSV injection prevention in exports
- **Decision coercion module:** Existing pattern for "coerce zero qty/price to HOLD" logic (to be extended for cooldown/frequency)

