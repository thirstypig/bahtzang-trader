# Daily Operations Guide

Your daily playbook for getting the most out of bahtzang.trader.

---

## Morning Routine (2 minutes)

Every market day (Mon-Fri), the bot runs automatically at **9:35 AM ET**. Here's what to check:

1. **Dashboard** -- Open the app and glance at Portfolio Summary. Check if your total value and daily P&L look reasonable.
2. **Trades** -- Click Trades in the sidebar. Look at the most recent entry. Did the bot execute a trade, hold, or get blocked by guardrails? Read Claude's reasoning to understand why.
3. **Bot Status** -- The green banner at the top of Dashboard tells you the bot is active. If it's red, the kill switch is on -- go to Settings to investigate.

That's it. The bot handles the rest.

---

## Weekly Review (5 minutes, Fridays)

1. **Analytics** -- Check your win rate, total return, and Sharpe ratio (once you have 60+ days of snapshots). Are returns trending up or down?
2. **Trades page** -- Scroll through the week's decisions. Are there patterns? Too many holds? Too many blocked trades?
3. **Guardrails check** -- Go to Settings. Are your limits still appropriate? If the bot is getting blocked too often, your limits might be too tight. If it's trading too aggressively, tighten them.

---

## How to Use Each Page

### Dashboard
Your home base. Shows portfolio value, cash, daily P&L, the last AI decision, how your money is allocated across stocks, and portfolio value over time. No actions needed -- just monitoring.

### Trades
Complete history of every bot decision. Each row shows the action (BUY/SELL/HOLD), ticker, confidence level, whether it was executed or blocked, and Claude's full reasoning. Use the CSV export button for tax reporting at year end.

### Analytics
Performance metrics powered by daily portfolio snapshots. The bot takes a snapshot at 4:05 PM ET each day. Key metrics:
- **Total Return** -- How much you've made or lost overall
- **Sharpe Ratio** -- Return per unit of risk (above 1.0 is good, above 2.0 is excellent). Needs 60+ days to be meaningful.
- **Max Drawdown** -- The worst peak-to-trough drop. This is your pain threshold.
- **Win Rate** -- Percentage of positive days. 55%+ is solid.

You can also click "Take Snapshot Now" to capture a snapshot manually.

### Settings
This is your control center. Three key areas:

**Risk Profile** -- Choose conservative, moderate, or aggressive. This auto-adjusts several guardrails at once:
- Conservative: 30% invested, 3% stop loss, 75% min confidence
- Moderate: 60% invested, 5% stop loss, 60% min confidence
- Aggressive: 90% invested, 8% stop loss, 45% min confidence

**Trading Goal** -- Tells Claude what kind of investments to look for:
- Maximize Returns -- growth stocks, momentum plays
- Steady Income -- dividend stocks, covered calls
- Capital Preservation -- treasuries, low-volatility
- Beat S&P 500 -- tactical sector rotation
- Swing Trading -- short-term technical setups
- Passive Index -- buy and hold ETFs

**Trading Frequency** -- How many times per day the bot runs:
- 1x/day: 9:35 AM ET (recommended for starting out)
- 3x/day: 9:35 AM, 1:00 PM, 3:45 PM ET
- 5x/day: 9:35, 10:30, 12:00, 1:30, 3:00 ET

**Guardrail Numbers** -- Fine-tune your limits:
- Max Total Invested -- cap on how much the bot can put into stocks
- Max Single Trade -- largest trade size
- Stop Loss -- auto-sell if a position drops this much
- Daily Order Limit -- max trades per day
- Min Confidence -- Claude must be this confident to trade
- Max Positions -- most stocks to hold at once

**Kill Switch** -- Emergency stop. Halts ALL trading immediately. Use it if something looks wrong. You can resume from the same page.

**Run Bot Now** -- Manually trigger one trading cycle. Useful for testing or when you want an immediate decision outside the schedule.

### Plans
Investment Plans let you split your portfolio into independent "pie slices." Each plan has its own:
- Budget and virtual cash tracking
- Trading goal and risk profile
- Separate AI analysis per plan
- Independent trade history and equity curve

**Creating a plan:**
1. Go to Plans and click "New Plan"
2. Name it (e.g., "Tech Growth" or "Dividend Income")
3. Set a budget (how much virtual cash to allocate)
4. Choose a trading goal and risk profile
5. Optionally set a target amount and date (Claude factors this into decisions)
6. Click Create

**Running a plan:**
- Plans run automatically on the same schedule as your main bot
- Or click "Run Now" on any plan's detail page for a manual cycle
- Each plan trades independently -- Plan A's decisions don't affect Plan B

**Monitoring a plan:**
- Click into any plan to see its virtual positions, equity curve, and trade history
- The donut chart on the Plans list shows how your budget is allocated across plans
- Export CSV per plan for tax tracking

### Backtest
Test trading strategies against historical data before risking real money:
1. Click "New Backtest"
2. Choose a strategy (SMA Crossover, RSI Mean Reversion, or Buy & Hold)
3. Pick tickers and date range
4. Set initial capital and risk parameters
5. Run it -- results appear with an equity curve and trade log

### Earnings
Shows upcoming earnings dates for stocks. The bot automatically reduces position sizes near earnings (50% reduction 0-1 days before, 70% reduction 2 days before) to protect against surprise moves.

### Audit Log
History of every settings change -- who changed what and when. Useful if you're wondering why a guardrail is set to a specific value.

---

## Getting Started Checklist

If you're just starting out with paper trading:

1. **Settings** -- Set risk profile to Conservative. Set trading goal to Beat S&P 500 or Passive Index.
2. **Settings** -- Set Max Total Invested to your test budget (e.g., $2,000). Set Max Single Trade to 20% of that ($400).
3. **Settings** -- Keep frequency at 1x/day to start.
4. **Settings** -- Click "Run Bot Now" to verify the pipeline works. Check Trades for the result.
5. **Wait** -- Let the bot run for 2-4 weeks on paper. Check Dashboard and Trades daily.
6. **Analytics** -- After 30+ trades, review performance. Adjust risk profile or goal if needed.
7. **Plans** -- Once comfortable, create 2-3 plans with different strategies to diversify.

---

## Tips

- **Don't panic on red days.** Even the best strategies have losing days. What matters is the trend over weeks and months.
- **Start conservative.** You can always increase risk later. Going the other direction is more painful.
- **Paper trade first.** Run at least 30 paper trades before putting real money in. The bot is in paper mode by default.
- **Check the reasoning.** Reading Claude's reasoning on the Trades page helps you understand and trust (or question) the bot's decisions.
- **Use plans to diversify.** Instead of one big portfolio, create separate plans for different goals. "Tech Growth" + "Dividend Income" + "Safe Haven" is a classic split.
- **The kill switch is your friend.** If anything feels off, hit it. You can always resume later.
