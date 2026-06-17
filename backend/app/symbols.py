"""Symbol classification shared across the pipeline (app-level infra).

Alpaca uses slash symbology for crypto pairs ("BTC/USD"). Crypto symbols need
different handling at several boundaries:
  - bars/prices come from CryptoHistoricalDataClient, NOT the stock client
    (the stock client silently returns a wrong instrument for "BTC" — see
    docs/solutions/logic-errors/crypto-tickers-in-stock-client-prompt.md)
  - orders require TimeInForce.GTC (Alpaca rejects DAY for crypto)
  - Alpha Vantage quotes/news and Finnhub earnings don't speak slash pairs
"""

# Alpaca's tradeable USD crypto pairs (paper + live). Kept as an allow-list so
# a typo like "BTC/USDT" fails loudly at the data layer instead of silently.
SUPPORTED_CRYPTO: frozenset[str] = frozenset({
    "BTC/USD", "ETH/USD", "SOL/USD", "DOGE/USD", "AVAX/USD", "LINK/USD",
    "LTC/USD", "BCH/USD", "UNI/USD", "AAVE/USD", "DOT/USD", "SHIB/USD",
    "XRP/USD",
})


def is_crypto(symbol: str) -> bool:
    """True for Alpaca slash-pair crypto symbols ('BTC/USD')."""
    return "/" in (symbol or "")
