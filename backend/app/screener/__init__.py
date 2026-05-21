"""Stock screener: ranks a large universe daily so Claude can research breadth.

Advisory by design — the screener produces a ranked candidate list (surfaced at
GET /screener and the /screener UI page) but does NOT auto-drive live trading.
Wiring its output into a portfolio's universe is a deliberate, separate step.
"""
