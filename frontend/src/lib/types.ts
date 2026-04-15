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

export interface Guardrails {
  risk_profile: "conservative" | "moderate" | "aggressive";
  trading_goal: TradingGoal;
  trading_frequency: "1x" | "3x" | "5x";
  max_total_invested: number;
  max_single_trade_size: number;
  stop_loss_threshold: number;
  daily_order_limit: number;
  min_confidence: number;
  max_positions: number;
  kill_switch: boolean;
  target_amount: number | null;
  target_date: string | null;
}

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

export interface EarningsEvent {
  symbol: string;
  report_date: string;
  fiscal_quarter: string | null;
  eps_estimate: number | null;
  revenue_estimate: number | null;
  hour: string | null;
}
