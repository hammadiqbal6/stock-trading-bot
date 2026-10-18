"""Validation metrics tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_bot.validation.metrics import (
    deflated_sharpe_ratio,
    performance_metrics,
    probabilistic_backtest_overfitting,
)


def test_performance_metrics_basic() -> None:
    rng = np.random.default_rng(0)
    rets = pd.Series(rng.normal(0.0005, 0.01, 252))
    m = performance_metrics(rets)
    assert m["n_obs"] == 252
    assert "sharpe" in m
    assert m["max_drawdown"] <= 0


def test_dsr_and_pbo() -> None:
    dsr = deflated_sharpe_ratio(1.2, n_obs=500, n_trials=50)
    assert 0 <= dsr["dsr"] <= 1
    pbo = probabilistic_backtest_overfitting([0.2, -0.1, 0.5, 0.0], n_strategies=10)
    assert 0 <= pbo["pbo_proxy"] <= 1
    assert pbo["n_folds"] == 4
