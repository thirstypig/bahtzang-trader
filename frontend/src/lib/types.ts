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

export interface Guardrails {
  max_total_invested: number;
  max_single_trade_size: number;
  stop_loss_threshold: number;
  daily_order_limit: number;
  kill_switch: boolean;
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
