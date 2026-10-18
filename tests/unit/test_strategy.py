"""Momentum strategy unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
from trading_bot.config.settings import StrategyConfig
from trading_bot.strategies.momentum import VolatilityScaledMomentumStrategy


def _synth_close(n: int = 320, symbols: list[str] | None = None) -> pd.DataFrame:
    symbols = symbols or ["AAA", "BBB", "CCC", "DDD"]
    idx = pd.bdate_range("2020-01-01", periods=n)
    rng = np.random.default_rng(42)
    data = {}
    for i, sym in enumerate(symbols):
        drift = 0.0008 if i % 2 == 0 else -0.0002
        rets = drift + rng.normal(0, 0.01, size=n)
        data[sym] = 100 * np.cumprod(1 + rets)
    return pd.DataFrame(data, index=idx)


def test_generates_nonnegative_weights() -> None:
    close = _synth_close()
    strat = VolatilityScaledMomentumStrategy(StrategyConfig(min_history_days=60, lookback_days=40))
    targets = strat.generate_targets(close)
    assert targets
    assert all(t.weight >= 0 for t in targets)
    assert sum(t.weight for t in targets) <= 1.01


def test_sentiment_block() -> None:
    close = _synth_close()
    strat = VolatilityScaledMomentumStrategy(StrategyConfig(min_history_days=60, lookback_days=40))
    # Force block on all by strongly negative sentiment after first pass symbols
    prelim = strat.generate_targets(close)
    if not prelim:
        return
    sym = prelim[0].symbol
    blocked = strat.generate_targets(close, sentiment={sym: -0.9})
    row = next(t for t in blocked if t.symbol == sym)
    assert row.blocked is True
    assert row.weight == 0.0


def test_insufficient_history_returns_empty() -> None:
    close = _synth_close(n=30)
    strat = VolatilityScaledMomentumStrategy()
    assert strat.generate_targets(close) == []
