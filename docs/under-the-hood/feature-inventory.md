---
id: DOC-053
type: guide
status: draft
phase: null
owner: james
tags: [trading-pipeline, risk, portfolios, strategies]
links: [PRD-002, DOC-017, DOC-018]
updated: 2026-10-19
---

# Feature inventory: what's actually live

Every feature in the system, in plain English, with one question answered for each:
**does it actually change a real trade today?** Written 2026-10-19, after Test 5 was
deactivated (zero portfolios active in prod). Judged against the new direction:
**stocks only, beat buy-and-hold SPY after all costs.**

**How "Live in trading?" was proven.** Every "Yes" names the line of code that calls it.
Every "No" comes from searching the whole backend for anything that calls it and finding
nothing (other than tests and the settings screen). Line numbers are as of commit `935de55`.

**Legend**
- **Yes (enforced)**: code blocks or changes the order no matter what Claude says.
- **Yes (prompt only)**: Claude is *told* about it in the prompt, but nothing in the code
  enforces it. Claude can ignore it, and the order still goes through.
- **No, setting is saved but never used**: you can change it in the UI, it's stored, and
  no trading code ever reads it.
- **No, built but not wired in**: the code exists and is tested, but nothing in the trading path calls it.

Short file names: `executor` = `backend/app/plans/executor.py`, `brain` = `backend/app/claude_brain.py`,
`sched` = `backend/app/scheduler.py`.

---

## 1. Trading decisions

| Feature | What it does | Live in trading? | Evidence | Suggested |
|---|---|---|---|---|
| Decision mode: `claude_decides` | Claude picks every buy/sell/hold. | Yes | `executor:393-408` | Decide. Test 5 used this and lost 9.3% while SPY gained 3.0% |
| Decision mode: `rules_decide` | A fixed formula picks trades and Claude is never called. | Yes | `executor:358-359` | Keep. Cheapest, and it does exactly what the backtest did |
| Decision mode: `rules_with_claude_oversight` | The formula proposes a trade, then Claude confirms or overrides each one. | Yes | `executor:360-392`, `brain:436` | Decide. Adds Claude cost, and its edge is unproven |
| Strategy: SMA crossover | Buys when the 50-day average crosses above the 200-day, and sells on the reverse. | Yes (rules modes only) | `strategies/registry.py:12`, called at `executor:201` | Decide. Backtest it after costs first |
| Strategy: RSI mean reversion | Buys oversold stocks (RSI<30) and sells overbought ones (RSI>70). | Yes (rules modes only) | `registry.py:13` | Decide. Backtest it after costs first |
| Strategy: buy-and-hold | Buys equal amounts on day 1 and holds. | Yes (rules modes only) | `registry.py:14` | Keep. This is the benchmark itself |
| Strategy: dual momentum | Holds whichever of US stocks (SPY), foreign stocks (VEU) or T-bills (BIL) has the best 12-month momentum, rebalanced monthly. | Yes (rules modes only) | `registry.py:15`, `executor:171-172` | Decide. VEU is foreign, so check that fits "stocks only" |
| Trading goal (`maximize_returns` etc.) | Picks the watchlist of tickers and the goal paragraph in Claude's prompt. | Yes (watchlist enforced, goal text prompt only) | `executor:674`, `brain:112,226` | Fix. No goal says "beat SPY after costs" |
| Risk profile (conservative/moderate/aggressive) | Selects a preset bundle of limits (see section 2). | Partly. Only some preset fields are enforced | `executor:109` | Fix. Most preset fields are prompt only |
| Target amount / date | Tells Claude "grow to $X by date Y" and to be more aggressive if behind. | Yes (prompt only) | `executor:115-118`, `brain:340-358` | Turn off. It pushes Claude to take more risk |
| Trading frequency (1x/3x/5x per day) | How many trading runs per day. | Partly. All portfolios run at the fastest frequency any active one asks for, and it's only read at server start | `sched:301-314`, called only at `sched:322` | Fix. Changing it does nothing until a restart |
| Screener (daily ranking) | Each morning at 7:30 it ranks about 650 large and mid-cap stocks by momentum, strength vs SPY, trend and volume. | Only through the screener feed below | `sched:283-290` | Keep. Useful research |
| Screener feed (`screener_top_n`) | Adds the screener's top N names to a portfolio's candidates and Claude's prompt. | Yes (Claude mode only. Rules modes ignore it) | `executor:311`, `executor:693-697` | Decide. Test 5 had it on (N=25) |
| Exit-only 3:30 PM cycle | Afternoon pass that can only sell or hold, and blocks any buy. | Yes (enforced) | `sched:374-382`, `executor:416-427` | Keep, but see the cooldown finding |
| Crypto support | Lets a portfolio trade pairs like BTC/USD (opt-in via extra tickers). | Yes, if a portfolio lists a crypto ticker | `brokers/alpaca.py:98-104`, `symbols.py:14` | Turn off. Out of scope (stocks only) |
| Decision clean-up (zero qty / bad price → hold) | Turns nonsense orders (0 shares, $0 price) into a logged hold. | Yes (enforced) | `executor:447`, `executor:459` | Keep |
| Every decision logged | Each buy/sell/hold, including blocked ones, is saved with Claude's reasoning. | Yes | `executor:583-603` | Keep |

## 2. Risk & safety

| Feature | What it does | Live in trading? | Evidence | Suggested |
|---|---|---|---|---|
| **Stop-loss %** (preset: 3/5/8%) | Meant to sell a position once it's down X%. | **Yes (prompt only)**. Claude is asked to sell losers at the 3:30 check. No order or code enforces it | `brain:288-299`. No other reader of `stop_loss_threshold` | Fix. This is the cause of Test 5's -10% to -24% exits |
| **Risk engine** (`risk.py`: stop set from typical daily price swing (ATR), size set from how much you risk) | Works out a stop price and a share count so each loss is about 1% of equity. | **No, built but not wired in** | `risk.py:25,37`. Only tests import `app.risk`. The single `place_order` call (`executor:555-560`) passes no `stop_price` | Fix. This is PRD-002's core |
| **Broker-held stop (OTO order)** | Alpaca holds a real stop order the moment a buy fills. | **No, built but not wired in** | `brokers/alpaca.py:100-110` supports it and no caller uses it. Not yet live-verified on paper | Fix. Wire it in with the risk engine |
| Min confidence (preset value) | Blocks buys where Claude's confidence is below 75/60/45%. | Yes (enforced, buys only) | `executor:543-545` | Keep |
| **Min confidence (per-portfolio setting)** | The confidence floor you set in the portfolio's strategy form. | **No, setting is saved but never used**. The preset value above wins | Read only by `plans/routes.py`. `executor:109` uses the preset | Fix or remove from UI |
| Max single trade size (preset 5/10/20% of budget, capped at 50%) | Biggest single buy allowed. | **Yes (prompt only)** | `executor:113`, `brain:240,372`. Not checked in the executor's validation (`executor:533-545`) | Fix. Enforce it in code |
| Max total invested (preset 30/60/90%) | Keeps part of the budget in cash. | **No, setting is saved but never used**. The executor overrides it to 100% of budget | `executor:112` | Decide. Is a cash reserve wanted? |
| Daily order limit (preset 3/5/10) | Max orders per day. | **Yes (prompt only)** | `brain:241,363`. Nothing in the executor counts against it | Fix. Enforce it in code |
| Max positions (preset 5/10/20) | Max number of holdings at once. | **Yes (prompt only)** | `brain:242,283`. The executor never checks it | Fix. Enforce it in code |
| Budget / virtual cash check | Blocks buys bigger than the portfolio's remaining cash or budget, and shrinks the size to fit cash. | Yes (enforced) | `executor:508-542` | Keep |
| Sell ownership check | A portfolio can't sell shares it doesn't own (protects the other portfolios). | Yes (enforced) | `executor:478-487` | Keep |
| Quarter-Kelly position sizing | Caps each buy using a "win rate" formula and Claude's confidence. | Yes (enforced) but its inputs are fake (see notes) | `executor:464-475`, `position_sizing.py:17-50` | Fix. Replace it with the risk engine's sizing |
| **Kelly fraction (per-portfolio setting)** | Your chosen fraction of the Kelly formula. | Rules modes only (used as max % per buy). In Claude mode the hard-coded 0.25 is used instead | `executor:215,234` vs `executor:466` (no fraction passed) | Fix. Same setting, two meanings |
| Earnings-proximity sizing | Cuts a buy to 50% if earnings are within 1 day, or 70% at 2 days. | Partly. It sits inside the Kelly formula, so it's skipped whenever Kelly falls back to its default size | `position_sizing.py:71-72` returns before `:88-95` | Fix. Make it a standalone rule |
| Cooldown (`cooldown_hours`, default 48h) | Blocks touching the same ticker again within N hours. | Yes (enforced), **including sells** | `constraints.py:46`, called at `executor:491-502` | Fix. It can block a stop-loss sell for 48h |
| Frequency cap | Max 5 buys and 5 sells per ticker per week. | Yes (enforced) | `constraints.py:61-67` | Keep |
| No-repeat-action guard | Meant to block buy→buy or sell→sell twice in a row. | **No, built but not wired in**. `last_action` is written and never read | `constraints.py:113` writes it. No reader | Turn off (delete the claim) |
| Circuit breaker, RED level | If the whole account loses 5% in a day or 10% in a week, it pauses every portfolio. | Yes (enforced), but **only on scheduled runs and the global "Run" button**. The per-portfolio "Run Now" skips it | `executor:765-773`. No breaker call in `plans/routes.py:501-531` | Fix. Close the bypass |
| Circuit breaker, YELLOW / ORANGE | Meant to halve sizes (yellow) or stop buys (orange). | **No, built but not wired in**. The executor only reacts to RED | `executor:768`. No other use of YELLOW/ORANGE | Turn off, or wire them in |
| Circuit breaker "5 losing trades in a row" | Halts after a losing streak. | Yes, but it counts "sells with confidence <50%", not real losses | `circuit_breaker.py:90-120` | Fix. Use real realized P&L |
| **Circuit-breaker % (per-portfolio settings)** | Your daily/weekly loss limits per portfolio. | **No, setting is saved but never used**. The breaker is called with `config={}` and uses fixed 5%/10% | `executor:766`, `circuit_breaker.py:33-34` | Fix. Also a unit bug: stored as `-5.0`, the code expects `0.05`. Wiring it naively would trip the breaker on every run |
| **PDT rule (pattern day trader) check** | Blocks a 4th day trade in 5 business days (a broker rule for accounts under $25k). | **No, built but not wired in** | `compliance.py:49`. Only tests call it | Fix before going live with $200 |
| **Wash-sale check + `respect_wash_sale` toggle** | Flags rebuying a stock within 30 days of selling it at a loss (that loss can't be claimed on taxes). | **No, built but not wired in**, and the toggle is **saved but never used** | `compliance.py:94`. Only tests call it. The toggle is read only by `plans/routes.py` | Decide. Matters for "after costs" once live |
| Kill switch (per portfolio `is_active`) | Pauses one portfolio. | Yes (enforced) | `executor:776`, `plans/routes.py:513-514` | Keep |

## 3. Data sources (what Claude and the strategies see)

| Feature | What it does | Live in trading? | Evidence | Suggested |
|---|---|---|---|---|
| Alpaca account + prices | Real positions, balance, and most prices. | Yes | `executor:659-662`, `executor:722-735` | Keep |
| Alpha Vantage quotes | Prices for held positions (free tier, often rate-limited). | Yes (Alpaca fills in when it fails) | `executor:714` | Decide. Could rely on Alpaca alone |
| Alpha Vantage news | Recent headlines passed to Claude. | Yes (prompt only) | `executor:715` | Decide. Unproven edge, costs API quota |
| Technical indicators (RSI/MACD/Bollinger/moving averages/ATR) | Chart indicators for every candidate. | Yes. A Claude prompt input, and what the rules strategies run on | `executor:716`, `executor:194` | Keep. ATR is needed by the risk engine |
| Sector rotation | Shows which of the 11 sector funds are beating SPY. | Yes (prompt only) | `executor:717,738` | Decide. Prompt noise unless proven |
| Earnings calendar (Finnhub, 7 AM refresh) | Upcoming earnings dates, shown to Claude and used for sizing. | Yes (prompt + sizing, see section 2) | `sched:253-270`, `executor:465,739` | Keep |
| Company profile hover card | Name and sector when you hover over a ticker. | N/A (dashboard only) | `company.py` | Keep |
| Schwab broker (backup) | Alternate broker connection. | **No, built but not wired in** | `brokers/schwab.py`, `schwab_client.py`. No importers | Turn off |

## 4. Research tools

| Feature | What it does | Live in trading? | Evidence | Suggested |
|---|---|---|---|---|
| Backtester | Replays a strategy over past prices. | Separate tool (its price cache also feeds the rules modes) | `backtest/engine.py`, `executor:150` | Fix. It models **no trading costs** (fees or the cost of filling at a worse price), so it can't test "after costs" |
| Forex tool | Nick Shawn's swing-zone forex backtester. | Separate tool | No imports outside `forex/` except router and model registration | Keep, siloed. Not in scope |
| Screener page | Read-only view of the daily ranking. | N/A (dashboard only) | `/screener` | Keep |

## 5. Dashboard & admin

| Feature | What it does | Live in trading? | Evidence | Suggested |
|---|---|---|---|---|
| Account snapshot (4:05 PM) | Saves end-of-day account value and the SPY close. | Yes, indirectly. The circuit breaker reads it | `sched:184-238`, `circuit_breaker.py:39-44` | Keep |
| Portfolio snapshots (4:06 PM) | Saves each active portfolio's value for its equity curve. | N/A (dashboard only) | `sched:154-161`, `plans/snapshots.py:20` | Keep |
| Equity curve vs SPY | Chart of account value against SPY. | N/A (dashboard only) | `components/EquityCurveChart.tsx:30-42` | Keep. It's the benchmark view. Note it's account-level and shows no costs |
| Analytics metrics | Sharpe and Sortino (return per unit of risk), worst drop (drawdown), win rate, profit factor. | N/A (dashboard only) | `routes/portfolio.py:9`, `backtest/engine.py:10` | Keep. Add an "excess return vs SPY" metric |
| Slack trade alerts | Posts each non-hold trade to Slack. | N/A (notification) | `executor:801` | Keep |
| Slack daily summary (4:10 PM) | End-of-day count and P&L in Slack. | N/A (notification) | `sched:138` | Keep |
| Slack kill-switch alert | Meant to post when a kill switch flips. | **No, built but not wired in** | `notifier.py:60`. No callers | Fix. Silent auto-pauses are dangerous |
| Pages: `/` dashboard | Account overview. | N/A | | Keep |
| `/portfolios` (list, detail, new) | Create, configure and pause portfolios. | N/A (it's where settings are edited) | | Keep. Hide the settings that are saved but never used |
| `/trades`, `/audit-log` | Trade history with Claude's reasoning. | N/A | | Keep |
| `/analytics` | Metrics + charts. | N/A | | Keep |
| `/backtest` | Run backtests. | N/A | | Keep |
| `/earnings` | Earnings calendar. | N/A | | Keep |
| `/screener` | Daily ranking. | N/A | | Keep |
| `/forex` | Forex backtester for Nick. | Separate tool | | Keep, siloed |
| `/markets` | Static reference: what's tradeable now or later. | N/A | | Turn off. Out of scope now |
| `/status`, `/errors` | System health and recent backend errors. | N/A | | Keep |
| `/docs`, `/todos`, `/roadmap`, `/changelog`, `/concepts`, `/about`, `/testing` | Internal knowledge-base and admin pages. | N/A | | Keep. `/concepts` and `/about` are optional |
| `/settings` | Timezone display preference. | N/A | | Keep |

## 6. Infrastructure

| Feature | What it does | Live in trading? | Evidence | Suggested |
|---|---|---|---|---|
| Scheduler | Runs trades at 10:00 (plus 13:00/15:45 or more at 3x/5x), the 3:30 exit check, and the 4:05/4:06/4:10 snapshots and summary. | Yes | `sched:28-32`, `sched:317-394` | Keep |
| Per-portfolio locks + one-order-at-a-time lock | Stops two runs from spending the same cash twice. | Yes | `executor:284`, `brokers/alpaca.py:114` | Keep |
| Login (Google via Supabase) + email allow-list | Only you (and listed emails) can use the app. | N/A | `auth.py` | Keep |
| Rate limits | Max 2 manual runs per minute. | N/A | `plans/routes.py:502` | Keep |
| Railway hosting, Supabase database, CI, pre-commit tests | Deploy, storage, safety net. | N/A | CLAUDE.md | Keep |

---

## Top findings

1. **No stop-loss exists in code.** The 3/5/8% "stop-loss" is only a sentence in Claude's 3:30 prompt (`claude_brain.py:288-299`). The real-stop machinery (`risk.py` + Alpaca stop orders) is built and tested but has no caller. This is why Test 5's losers ran to -10% to -24%.
2. **The 48-hour cooldown also blocks sells** (`constraints.py:46`, applied to every non-hold at `executor.py:491`). Even if Claude decides to cut a loser the day after buying it, the code turns that sell into a hold.
3. **Four per-portfolio safety settings do nothing:** min confidence, circuit-breaker daily/weekly %, and respect-wash-sale. They're saved and shown in the UI, but the executor uses fixed preset values or never checks them. Kelly fraction only works in rules modes. Separately, the circuit-breaker settings are stored in the wrong units (`-5.0` vs `0.05`), so wiring them in as-is would halt trading on every run.
4. **Most preset limits are only requests to Claude.** Max trade size, max positions and daily order limit are written into the prompt but never checked in code. Max total invested is silently raised to 100% of budget.
5. **The circuit breaker is weaker than it looks.** Only RED does anything (YELLOW/ORANGE do nothing). The per-portfolio "Run Now" button skips it entirely. Its "losing streak" rule counts low-confidence sells, not actual losses.
6. **Nothing measures "after costs".** The backtester models no fees or slippage, Kelly sizing's "win rate" is really Claude's confidence (`position_sizing.py:37-40`), and the PDT and wash-sale checks have no callers. Fix these before trusting any result against SPY or going live.
