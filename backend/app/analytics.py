"""Portfolio analytics — compute metrics from daily snapshots."""

import math
from dataclasses import asdict, dataclass


@dataclass
class PortfolioMetrics:
    total_return_pct: float
    sharpe_ratio: float | None
    sharpe_confidence: str
    sortino_ratio: float | None
    max_drawdown_pct: float
    max_drawdown_days: int
    win_rate_pct: float
    profit_factor: float | None
    best_day_pct: float
    worst_day_pct: float
    volatility_annual_pct: float
    num_trading_days: int

    def to_dict(self) -> dict:
        return asdict(self)


def compute_metrics(
    equities: list[float],
    risk_free_annual: float = 0.05,
) -> PortfolioMetrics:
    """Compute all portfolio metrics from a time series of daily equity values."""
    n = len(equities)

    if n < 2:
        return PortfolioMetrics(
            total_return_pct=0,
            sharpe_ratio=None,
            sharpe_confidence="insufficient_data",
            sortino_ratio=None,
            max_drawdown_pct=0,
            max_drawdown_days=0,
            win_rate_pct=0,
            profit_factor=None,
            best_day_pct=0,
            worst_day_pct=0,
            volatility_annual_pct=0,
            num_trading_days=n,
        )

    # Daily returns
    daily_returns = [(equities[i] / equities[i - 1]) - 1 for i in range(1, n)]
    rf_daily = risk_free_annual / 252
    excess = [r - rf_daily for r in daily_returns]

    # Total return
    total_return = (equities[-1] / equities[0] - 1.0) * 100

    # Volatility
    mean_excess = sum(excess) / len(excess)
    variance = sum((r - mean_excess) ** 2 for r in excess) / (len(excess) - 1)
    vol_daily = math.sqrt(variance) if variance > 0 else 0
    vol_annual = vol_daily * math.sqrt(252) * 100

    # Sharpe
    sharpe = None
    confidence = "insufficient_data"
    if n > 5 and vol_daily > 0:
        sharpe_daily = mean_excess / vol_daily
        sharpe = round(sharpe_daily * math.sqrt(252), 2)
        t_stat = sharpe_daily * math.sqrt(n - 1)
        if n < 30:
            confidence = "low"
        elif t_stat < 1.96:
            confidence = "moderate"
        else:
            confidence = "high"

    # Sortino (only penalize downside volatility)
    sortino = None
    downside = [r for r in excess if r < 0]
    if len(downside) > 1:
        downside_variance = sum(r ** 2 for r in downside) / (len(downside) - 1)
        downside_std = math.sqrt(downside_variance)
        if downside_std > 0:
            sortino = round(mean_excess / downside_std * math.sqrt(252), 2)

    # Max drawdown
    peak = equities[0]
    max_dd = 0.0
    peak_idx = 0
    max_dd_days = 0
    for i in range(1, n):
        if equities[i] > peak:
            peak = equities[i]
            peak_idx = i
        dd = (equities[i] - peak) / peak
        if dd < max_dd:
            max_dd = dd
        if equities[i] < peak:
            max_dd_days = max(max_dd_days, i - peak_idx)

    # Win rate and profit factor (from daily returns)
    wins = [r for r in daily_returns if r > 0]
    losses = [r for r in daily_returns if r < 0]
    win_rate = len(wins) / len(daily_returns) * 100 if daily_returns else 0

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None

    return PortfolioMetrics(
        total_return_pct=round(total_return, 2),
        sharpe_ratio=sharpe,
        sharpe_confidence=confidence,
        sortino_ratio=sortino,
        max_drawdown_pct=round(max_dd * 100, 2),
        max_drawdown_days=max_dd_days,
        win_rate_pct=round(win_rate, 1),
        profit_factor=profit_factor,
        best_day_pct=round(max(daily_returns) * 100, 2) if daily_returns else 0,
        worst_day_pct=round(min(daily_returns) * 100, 2) if daily_returns else 0,
        volatility_annual_pct=round(vol_annual, 2),
        num_trading_days=n,
    )
