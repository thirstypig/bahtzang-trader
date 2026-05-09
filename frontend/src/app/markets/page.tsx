const CURRENT: Product[] = [
  {
    name: "US Common Stocks",
    description:
      "Individual equities listed on NYSE, NASDAQ, and AMEX. Claude picks single-stock positions based on technical indicators, news sentiment, and portfolio goals.",
    instruments: ["NVDA", "META", "AAPL", "MSFT", "TSLA", "AMZN", "any NYSE/NASDAQ ticker"],
    broker: "Alpaca",
    status: "live",
    notes: "Fractional shares supported (minimum $1 order).",
  },
  {
    name: "US ETFs",
    description:
      "Exchange-traded funds — sector ETFs, broad-market index funds, and thematic baskets. Used for diversification and sector-rotation strategies.",
    instruments: ["SPY", "QQQ", "XLK", "XLE", "IWM", "GLD", "all major ETFs"],
    broker: "Alpaca",
    status: "live",
    notes: "Sector-rotation signals compare 11 SPDR sector ETFs vs SPY monthly performance.",
  },
];

const NEAR_TERM: Product[] = [
  {
    name: "Crypto",
    description:
      "Bitcoin, Ethereum, and major altcoins. Alpaca's crypto API uses the same order interface as equities — minimal integration lift.",
    instruments: ["BTC", "ETH", "SOL", "DOGE"],
    broker: "Alpaca Crypto",
    status: "planned",
    notes: "24/7 trading; no PDT rules. Requires separate risk parameters (higher volatility).",
  },
  {
    name: "Covered Calls / Basic Options",
    description:
      "Single-leg options strategies — covered calls on held positions and cash-secured puts. Generates premium income for the Steady Income goal.",
    instruments: ["Calls + puts on held equities"],
    broker: "Alpaca Options",
    status: "planned",
    notes: "Alpaca supports basic options. Requires PDT + wash-sale rule updates for options.",
  },
];

const FUTURE: Product[] = [
  {
    name: "Forex (Live Trading)",
    description:
      "Currency pairs traded 24/5. An independent swing-zone backtester is already built (/forex). Live execution is the next step once the strategy shows consistent edge.",
    instruments: ["EUR/USD", "GBP/USD", "USD/JPY", "major pairs"],
    broker: "TBD (Interactive Brokers / OANDA)",
    status: "future",
    notes: "Backtest framework complete. Live execution gated on 30+ consistent backtest runs.",
  },
  {
    name: "International Equities",
    description:
      "Direct access to non-US stocks via ADRs (American Depositary Receipts) or an international broker. Unlocks exposure to European, Asian, and emerging-market companies.",
    instruments: ["BABA", "NVO", "ASML", "TSM", "direct international tickers"],
    broker: "Schwab International / Interactive Brokers",
    status: "future",
    notes: "ADRs available now via Alpaca. Direct international access needs a second broker integration.",
  },
  {
    name: "US Treasuries & Bonds",
    description:
      "Treasury bills, notes, and bonds for capital preservation goals. Lower return ceiling but acts as a portfolio stabilizer during equity drawdowns.",
    instruments: ["T-bills", "2Y/5Y/10Y/30Y Treasuries", "TLT", "IEF"],
    broker: "Schwab (treasury auctions) / ETF proxy via Alpaca",
    status: "future",
    notes: "Bond ETFs (TLT, IEF) available today via Alpaca. Direct treasury access via Schwab API.",
  },
  {
    name: "Commodities",
    description:
      "Gold, oil, agriculture futures via ETFs or commodity-linked instruments. Adds inflation hedging and non-correlated return streams.",
    instruments: ["GLD", "SLV", "USO", "DBA", "commodity ETFs"],
    broker: "Alpaca (ETF proxy) / futures broker TBD",
    status: "future",
    notes: "Commodity ETFs (GLD, USO) available now via Alpaca. Futures require a separate FCM integration.",
  },
];

interface Product {
  name: string;
  description: string;
  instruments: string[];
  broker: string;
  status: "live" | "planned" | "future";
  notes: string;
}

const STATUS_STYLES: Record<Product["status"], string> = {
  live: "bg-pos/15 text-pos",
  planned: "bg-accent/15 text-accent",
  future: "bg-card-alt/60 text-muted",
};

const STATUS_LABELS: Record<Product["status"], string> = {
  live: "Live",
  planned: "Planned",
  future: "Future",
};

function ProductCard({ p }: { p: Product }) {
  return (
    <div className="bz-glass rounded-xl p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-primary">{p.name}</h3>
          <p className="mt-0.5 text-xs text-muted">{p.broker}</p>
        </div>
        <span
          className={`shrink-0 rounded px-2 py-0.5 text-xs font-semibold uppercase ${STATUS_STYLES[p.status]}`}
        >
          {STATUS_LABELS[p.status]}
        </span>
      </div>
      <p className="mb-3 text-sm text-secondary">{p.description}</p>
      <div className="mb-2 flex flex-wrap gap-1.5">
        {p.instruments.map((inst) => (
          <span
            key={inst}
            className="rounded bg-card-alt/60 px-2 py-0.5 font-mono text-xs text-secondary"
          >
            {inst}
          </span>
        ))}
      </div>
      <p className="text-xs text-muted">{p.notes}</p>
    </div>
  );
}

export default function MarketsPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-primary">Markets</h1>
        <p className="mt-1 text-sm text-muted">
          Financial products available now, in progress, and on the roadmap
        </p>
      </div>

      <div className="space-y-10">
        {/* Live */}
        <section>
          <div className="mb-4 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-pos" />
            <h2 className="text-lg font-semibold text-primary">Currently Trading</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {CURRENT.map((p) => (
              <ProductCard key={p.name} p={p} />
            ))}
          </div>
        </section>

        {/* Planned */}
        <section>
          <div className="mb-4 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-accent" />
            <h2 className="text-lg font-semibold text-primary">Near-Term Additions</h2>
          </div>
          <p className="mb-4 text-sm text-muted">
            Alpaca already supports these — integration is a sprint, not a project.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {NEAR_TERM.map((p) => (
              <ProductCard key={p.name} p={p} />
            ))}
          </div>
        </section>

        {/* Future */}
        <section>
          <div className="mb-4 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-muted" />
            <h2 className="text-lg font-semibold text-primary">Future Exploration</h2>
          </div>
          <p className="mb-4 text-sm text-muted">
            Gated on live-trading results and additional broker integrations.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {FUTURE.map((p) => (
              <ProductCard key={p.name} p={p} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
