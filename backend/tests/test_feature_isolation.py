"""Feature-module isolation guard (CLAUDE.md "Feature Module Isolation").

A feature package must not import another feature package's internals. Shared
infrastructure lives at the app level (app.strategies, app.bars, app.risk, ...).

ALLOWED lists the designed integration points: the portfolio pipeline (plans) is
the one consumer of the earnings and screener feeds. Anything else is a violation.
"""

import pathlib
import re

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
FEATURES = ["backtest", "earnings", "plans", "forex", "screener"]
ALLOWED = {
    ("plans", "earnings"),   # earnings-proximity sizing + prompt CSV feed
    ("plans", "screener"),   # screener top-N feed into opted-in portfolios
}
IMPORT = re.compile(r"^\s*(?:from|import)\s+app\.(\w+)", re.M)


def test_no_cross_feature_imports():
    violations = []
    for feature in FEATURES:
        for path in (APP / feature).rglob("*.py"):
            for target in IMPORT.findall(path.read_text()):
                if target in FEATURES and target != feature and (feature, target) not in ALLOWED:
                    violations.append(f"{path.relative_to(APP)} imports app.{target}")
    assert violations == [], "\n".join(violations)
