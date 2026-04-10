export interface Todo {
  id: string;
  title: string;
  description?: string;
  status: "todo" | "in-progress" | "done";
  priority: "urgent" | "high" | "medium" | "low";
  dueDate?: string;
  category: "setup" | "trading" | "risk" | "feature" | "research";
  addedDate: string;
}

export const todos: Todo[] = [
  // SETUP — get the bot actually trading
  {
    id: "deposit-funds",
    title: "Deposit funds into brokerage account",
    description: "Fund your Schwab or Alpaca account. Start with paper trading before going live.",
    status: "todo",
    priority: "urgent",
    category: "setup",
    addedDate: "2026-04-10",
  },
  {
    id: "alpaca-account",
    title: "Create Alpaca Markets account",
    description: "Sign up at alpaca.markets. Get API key + secret. Enable paper trading first.",
    status: "todo",
    priority: "urgent",
    category: "setup",
    addedDate: "2026-04-10",
  },
  {
    id: "schwab-api-creds",
    title: "Get Schwab API credentials",
    description: "Apply for Schwab Developer API access at developer.schwab.com. May take 1-2 weeks for approval.",
    status: "todo",
    priority: "high",
    category: "setup",
    addedDate: "2026-04-10",
  },
  {
    id: "alpha-vantage-key",
    title: "Get Alpha Vantage API key",
    description: "Free tier: 25 requests/day. Premium ($49/mo) for unlimited. Sign up at alphavantage.co.",
    status: "todo",
    priority: "high",
    category: "setup",
    addedDate: "2026-04-10",
  },
  {
    id: "supabase-google-auth",
    title: "Verify Google OAuth redirect URLs",
    description: "Google Cloud Console → Credentials → OAuth client: add www.bahtzang.com and Supabase callback URL to authorized redirects.",
    status: "todo",
    priority: "high",
    category: "setup",
    addedDate: "2026-04-10",
  },
  {
    id: "cors-production",
    title: "Confirm CORS_ORIGINS is set to https://www.bahtzang.com",
    description: "Railway → bahtzang-backend → Variables → CORS_ORIGINS should be https://www.bahtzang.com",
    status: "todo",
    priority: "high",
    category: "setup",
    addedDate: "2026-04-10",
  },

  // TRADING — before going live
  {
    id: "paper-trade-30",
    title: "Run 30 paper trades before going live",
    description: "Paper trading mode validates Claude's decisions without risking real money. Minimum 30 trades or 2 weeks.",
    status: "todo",
    priority: "urgent",
    category: "trading",
    addedDate: "2026-04-10",
  },
  {
    id: "test-manual-cycle",
    title: "Test a manual bot cycle via POST /run",
    description: "After broker API is connected, trigger one cycle manually and verify the full pipeline works.",
    status: "todo",
    priority: "high",
    category: "trading",
    addedDate: "2026-04-10",
  },

  // RISK — must do before real money
  {
    id: "pdt-check",
    title: "Understand Pattern Day Trader rule",
    description: "If account < $25k equity: max 3 day trades in 5 business days. Bot must respect this.",
    status: "todo",
    priority: "high",
    category: "risk",
    addedDate: "2026-04-10",
  },
  {
    id: "set-guardrails",
    title: "Configure guardrails for your risk tolerance",
    description: "Settings page: set max total invested, max single trade size, stop loss %, daily order limit.",
    status: "todo",
    priority: "high",
    category: "risk",
    addedDate: "2026-04-10",
  },

  // FEATURE — roadmap items to build
  {
    id: "build-alpaca-integration",
    title: "Build Alpaca broker integration",
    description: "Phase 1: Create alpaca_client.py with stocks, ETFs, options, crypto support.",
    status: "todo",
    priority: "high",
    category: "feature",
    addedDate: "2026-04-10",
  },
  {
    id: "build-risk-mgmt",
    title: "Build risk management subsystem",
    description: "Phase 3: VaR, Kelly criterion, circuit breakers, PDT compliance.",
    status: "todo",
    priority: "high",
    category: "feature",
    addedDate: "2026-04-10",
  },
  {
    id: "build-enhanced-brain",
    title: "Enhance Claude's trading brain",
    description: "Phase 2: Two-tier screening, technical indicators, sector rotation, earnings calendar.",
    status: "todo",
    priority: "medium",
    category: "feature",
    addedDate: "2026-04-10",
  },

  // RESEARCH
  {
    id: "research-penny-stocks",
    title: "Research penny stocks & OTC trading platforms",
    description: "Zero-commission options, API availability, risks for AI bot.",
    status: "in-progress",
    priority: "medium",
    category: "research",
    addedDate: "2026-04-10",
  },
  {
    id: "research-intl-markets",
    title: "Research international markets & currencies",
    description: "Tokyo, London, Hong Kong exchanges. ADRs vs direct access. Forex platforms.",
    status: "in-progress",
    priority: "medium",
    category: "research",
    addedDate: "2026-04-10",
  },
  {
    id: "research-alts",
    title: "Research alternative investments",
    description: "REITs, real estate crowdfunding, micro-VC, commodities, DeFi yield, art/collectibles.",
    status: "in-progress",
    priority: "medium",
    category: "research",
    addedDate: "2026-04-10",
  },
];
