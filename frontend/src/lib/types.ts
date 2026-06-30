export interface Trade {
  id: number;
  timestamp: string;
  ticker: string;
  action: "buy" | "sell" | "hold";
  quantity: number;
  price: number | null;
  claude_reasoning: string | null;
  confidence: number | null;
  guardrail_passed: boolean;
  guardrail_block_reason: string | null;
  executed: boolean;
}

export interface Position {
  instrument: {
    symbol: string;
    assetType: string;
  };
  longQuantity: number;
  marketValue: number;
  averagePrice: number;
  currentDayProfitLoss: number;
  currentDayProfitLossPercentage: number;
}

export interface Balance {
  cash_available: number;
  total_value: number;
}

export interface Portfolio {
  positions: Position[];
  balance: Balance;
}

export type TradingGoal =
  | "maximize_returns"
  | "steady_income"
  | "capital_preservation"
  | "beat_sp500"
  | "swing_trading"
  | "passive_index";

export interface CycleResult {
  trade_id: number;
  action: string;
  ticker: string;
  quantity: number;
  price: number | null;
  executed: boolean;
  guardrail_passed: boolean;
  guardrail_block_reason: string | null;
  reasoning: string;
  confidence: number;
}

// ---------------------------------------------------------------------------
// Backtest
// ---------------------------------------------------------------------------

export interface StrategyInfo {
  id: string;
  name: string;
  description: string;
  params: { key: string; label: string; type: string; default: unknown }[];
}

export interface BacktestItem {
  id: number;
  config_id: number;
  name: string;
  strategy: string;
  tickers: string[];
  start_date: string;
  end_date: string;
  initial_capital: number;
  params: Record<string, unknown>;
  max_position_pct: number;
  max_positions: number;
  stop_loss_pct: number;
  status: "pending" | "running" | "completed" | "failed";
  total_return_pct: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown_pct: number | null;
  win_rate_pct: number | null;
  profit_factor: number | null;
  total_trades: number | null;
  error_message: string | null;
}

export interface BacktestDetail extends BacktestItem {
  equity_curve: { date: string; equity: number }[];
  trades_log: {
    date: string;
    ticker: string;
    action: string;
    quantity: number;
    price: number;
    reason: string;
    confidence: number;
  }[];
  config: {
    id: number;
    name: string;
    strategy: string;
    tickers: string[];
    start_date: string;
    end_date: string;
    initial_capital: number;
    params: Record<string, unknown>;
  };
}

// ---------------------------------------------------------------------------
// Earnings
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Plans
// ---------------------------------------------------------------------------

export interface StrategyAuditEntry {
  id: number;
  timestamp: string;
  user_email: string;
  action: string;
  old_value: string | null;
  new_value: string | null;
  reason: string | null;
}

export interface PortfolioStrategy {
  cooldown_hours: number;
  min_confidence: number;
  respect_wash_sale: boolean;
  kelly_fraction: number;
  circuit_breaker_daily_pct: number;
  circuit_breaker_weekly_pct: number;
  audit_log: StrategyAuditEntry[];
}

export type DecisionMode =
  | "claude_decides"
  | "rules_decide"
  | "rules_with_claude_oversight";

export interface InvestmentPlan {
  id: number;
  name: string;
  budget: number;
  virtual_cash: number;
  trading_goal: TradingGoal;
  risk_profile: "conservative" | "moderate" | "aggressive";
  trading_frequency: "1x" | "3x" | "5x";
  target_amount: number | null;
  target_date: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  trade_count?: number;
  invested?: number;
  decision_mode: DecisionMode;
  strategy_id: string | null;
  strategy_params: Record<string, unknown>;
}

export interface PlanPosition {
  id: number;
  plan_id: number;
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  cost_basis: number;
  pnl: number;
  pnl_pct: number;
}

export interface PlanSnapshotData {
  date: string;
  budget: number;
  virtual_cash: number;
  invested_value: number;
  total_value: number;
  pnl: number;
  pnl_pct: number;
}

export interface EarningsEvent {
  symbol: string;
  report_date: string;
  fiscal_quarter: string | null;
  eps_estimate: number | null;
  revenue_estimate: number | null;
  hour: string | null;
}

// ---------------------------------------------------------------------------
// Oversight Activity
// ---------------------------------------------------------------------------

export interface OversightRecord {
  id: number;
  timestamp: string;
  ticker: string;
  rules_recommendation: {
    action: string;
    ticker?: string;
    quantity?: number;
    confidence?: number;
    reasoning?: string;
  };
  final_action: string;
  executed: boolean;
  diverged: boolean;
  claude_reasoning: string | null;
}

export interface OversightActivity {
  summary: {
    total: number;
    confirmed: number;
    overridden: number;
    confirmed_pct: number;
    overridden_pct: number;
  };
  records: OversightRecord[];
}

export type ForexEarlyExitMode = "none" | "progress" | "time_band";

export interface ForexBacktestCreate {
  name: string;
  symbols: string[];
  start_date: string;
  end_date: string;
  initial_equity: number;
  risk_pct: number;
  sl_buffer_pct: number;
  pivot_lookback_weeks: number;
  cluster_pct: number;
  early_exit_mode: ForexEarlyExitMode;
  early_exit_min_bars: number;
  early_exit_threshold_r: number;
}

export interface ForexBacktestSummary {
  id: number;
  name: string;
  created_at: string | null;
  status: string;
  error_message: string | null;
  symbols: string[];
  start_date: string;
  end_date: string;
  initial_equity: number;
  risk_pct: number;
  final_equity: number | null;
  total_return_pct: number | null;
  total_trades: number | null;
  win_rate_pct: number | null;
  profit_factor: number | null;
  max_drawdown_pct: number | null;
}

export interface ForexTrade {
  symbol: string;
  direction: "long" | "short";
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  stop_loss: number;
  take_profit: number;
  units: number;
  pnl_usd: number;
  exit_reason: string;
  zone_top: number;
  zone_bottom: number;
}

export interface ForexBacktestDetail extends ForexBacktestSummary {
  sl_buffer_pct: number;
  pivot_lookback_weeks: number;
  cluster_pct: number;
  early_exit_mode: ForexEarlyExitMode;
  early_exit_min_bars: number;
  early_exit_threshold_r: number;
  equity_curve: { date: string; equity: number }[];
  trades_log: ForexTrade[];
}

export interface ScreenerCandidate {
  rank: number;
  ticker: string;
  composite_score: number;
  momentum: number;
  rel_strength: number;
  trend_score: number;
  rsi: number;
  volatility: number;
  price: number;
}

export interface ScreenerRun {
  id: number;
  run_at: string;
  universe_size: number;
  scored_count: number;
  status: string;
  error: string | null;
}

export interface ScreenerResult {
  run: ScreenerRun | null;
  refreshing?: boolean;
  candidates: ScreenerCandidate[];
}

export interface CompanyProfile {
  ticker: string;
  name: string | null;
  industry: string | null;
  exchange: string | null;
  market_cap: number | null; // millions USD
  logo: string | null;
  currency: string | null;
  website: string | null;
  yahoo_url: string;
  source: "finnhub" | "none";
}
