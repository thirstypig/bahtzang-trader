export interface Concept {
  id: string;
  title: string;
  tab: "strategic" | "seo" | "integrations" | "ux";
  status: "exploring" | "planned" | "building" | "shipped";
  description: string;
  phases?: string[];
  roadmapSection?: string;
  details?: Record<string, string>;
}

export const concepts: Concept[] = [
  // Strategic
  {
    id: "multi-model-consensus",
    title: "Multi-Model Consensus",
    tab: "strategic",
    status: "exploring",
    description:
      "Use Sonnet as primary + Opus for high-stakes decisions (earnings, reversals). Require 2/3 supermajority for action; disagreement = HOLD.",
    phases: [
      "Small account (<$25k): Single Sonnet (current)",
      "Medium account ($25k-$100k): Sonnet + Opus for earnings",
      "Large account (>$100k): Full consensus with Haiku screening",
    ],
    roadmapSection: "/roadmap#claude-brain",
    details: {
      "Est. cost": "~$0.50-$2.00 per daily cycle with Sonnet",
      "Key risk": "Model disagreement may cause excessive holding",
    },
  },
  {
    id: "backtesting-framework",
    title: "Backtesting Framework",
    tab: "strategic",
    status: "planned",
    description:
      "Replay historical data through Claude to evaluate strategies before going live. Critical for building confidence in the bot's performance.",
    phases: [
      "Backtrader integration (most flexible for LLM)",
      "Date range selector + results dashboard",
      "Multiple backtest comparison view",
    ],
    roadmapSection: "/roadmap#backtesting",
    details: {
      Library: "Backtrader (Python) or Vectorbt (numpy-fast)",
      "Key rule": "Prevent lookahead bias — use i-1 data only",
    },
  },
  {
    id: "options-strategy-engine",
    title: "Options Strategy Engine",
    tab: "strategic",
    status: "exploring",
    description:
      "Extend the bot to trade options — covered calls on held positions, cash-secured puts for entry, and protective puts for downside protection.",
    details: {
      "Alpaca support": "Yes — options trading via same API",
      "Complexity": "High — Greeks, expiry management, assignment risk",
    },
  },
  {
    id: "crypto-24-7",
    title: "Crypto 24/7 Trading Mode",
    tab: "strategic",
    status: "exploring",
    description:
      "Alpaca supports crypto trading 24/7. Enable the bot to trade BTC/ETH outside market hours with a separate schedule and crypto-specific guardrails.",
    details: {
      "Schedule": "Every 4 hours, 24/7",
      "Separate guardrails": "Different volatility thresholds for crypto",
    },
  },
  {
    id: "social-sentiment",
    title: "Social Sentiment Integration",
    tab: "strategic",
    status: "exploring",
    description:
      "Feed Reddit/X sentiment data to Claude alongside technical indicators. Useful for meme stocks and crypto momentum.",
    roadmapSection: "/roadmap#claude-brain",
    details: {
      "Data sources": "Reddit API, X API, StockTwits",
      Concern: "Sentiment data is noisy — Claude may overweight it",
    },
  },

  // SEO Pages
  {
    id: "seo-ai-trading-guide",
    title: "AI Trading Bot Guide",
    tab: "seo",
    status: "planned",
    description:
      "Comprehensive guide: 'How to Build an AI Trading Bot with Claude in 2026'. Target keywords: ai trading bot, algorithmic trading, claude ai.",
    details: {
      Keywords: "ai trading bot, algorithmic trading, llm trading",
      "Word count": "3,000-5,000",
      Type: "Long-form guide with code examples",
    },
  },
  {
    id: "seo-claude-trading",
    title: "Claude for Trading",
    tab: "seo",
    status: "planned",
    description:
      "Deep dive into using Claude Sonnet for stock analysis and trade decisions. Include prompt engineering tips and confidence calibration.",
    details: {
      Keywords: "claude ai trading, llm stock trading, ai stock analysis",
      "Word count": "2,000-3,000",
      Type: "Technical tutorial",
    },
  },
  {
    id: "seo-paper-trading",
    title: "Paper Trading Tutorial",
    tab: "seo",
    status: "planned",
    description:
      "Step-by-step guide to paper trading with Alpaca API. From setup to first simulated trade.",
    details: {
      Keywords: "paper trading alpaca, simulated trading, practice trading",
      "Word count": "1,500-2,500",
      Type: "Beginner tutorial",
    },
  },

  // Integrations
  {
    id: "alpaca-data-api",
    title: "Alpaca Data API (OHLCV)",
    tab: "integrations",
    status: "planned",
    description:
      "Replace Alpha Vantage for historical OHLCV data. 200 req/min (vs 25/day). Already have alpaca-py SDK installed.",
    details: {
      "API available": "Yes — StockHistoricalDataClient in alpaca-py",
      Priority: "High — blocks technical indicators feature",
      "Free tier": "Includes historical bars with paper trading account",
    },
  },
  {
    id: "finnhub-earnings",
    title: "Finnhub Earnings Calendar",
    tab: "integrations",
    status: "exploring",
    description:
      "Free earnings calendar API (60 req/min). Filter out stocks reporting within 14 days to reduce earnings surprise risk.",
    details: {
      "API available": "Yes — /calendar/earnings endpoint",
      Priority: "Medium",
      "Free tier": "60 calls/min",
    },
  },
  {
    id: "tradingview-charts",
    title: "TradingView Chart Embeds",
    tab: "integrations",
    status: "exploring",
    description:
      "Embed TradingView advanced charts on the dashboard for visual technical analysis alongside Claude's decisions.",
    details: {
      "API available": "Yes — widget/embed (no API key needed)",
      Priority: "Low — nice-to-have visual enhancement",
    },
  },
  {
    id: "discord-notifications",
    title: "Discord Webhook (Alt Notifications)",
    tab: "integrations",
    status: "exploring",
    description:
      "Alternative to Slack for trade notifications. Same webhook pattern, different platform.",
    details: {
      "API available": "Yes — incoming webhook URL",
      Priority: "Low — Slack already implemented",
    },
  },

  // UX Mockups
  {
    id: "mobile-pwa",
    title: "Mobile PWA Layout",
    tab: "ux",
    status: "exploring",
    description:
      "Responsive dashboard for checking trades from your phone. Add PWA manifest for install-to-homescreen.",
    details: {
      Approach: "Responsive Tailwind breakpoints + manifest.json",
      "Key screens": "Dashboard summary, recent trades, kill switch",
    },
  },
  {
    id: "theme-toggle",
    title: "Dark/Light Theme Toggle",
    tab: "ux",
    status: "planned",
    description:
      "System preference detection with manual override. Store preference in localStorage.",
    details: {
      Approach: "CSS variables + Tailwind dark: prefix",
      Storage: "localStorage + system prefers-color-scheme",
    },
  },
  {
    id: "allocation-sunburst",
    title: "Portfolio Allocation Sunburst",
    tab: "ux",
    status: "exploring",
    description:
      "Interactive sunburst chart showing portfolio allocation by sector > ticker > position size.",
    details: {
      Library: "Recharts (existing) or visx for complex viz",
      "Data source": "Broker positions API",
    },
  },
];
