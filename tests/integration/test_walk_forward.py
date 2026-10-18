"""Walk-forward validation on synthetic prices (no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_bot.config.settings import Settings
from trading_bot.validation.walk_forward import run_walk_forward


def test_walk_forward_synthetic(tmp_path) -> None:
    idx = pd.bdate_range("2019-01-01", periods=900)
    rng = np.random.default_rng(1)
    cols = {}
    for i, sym in enumerate(["SPY", "QQQ", "TLT", "AAPL", "MSFT"]):
        rets = 0.0003 + rng.normal(0, 0.01, len(idx))
        cols[sym] = 100 * np.cumprod(1 + rets)
    close = pd.DataFrame(cols, index=idx)

    settings = Settings(
        trading_mode="backtest",
        data_dir=tmp_path / "d",
        cache_dir=tmp_path / "c",
        model_dir=tmp_path / "m",
        log_dir=tmp_path / "l",
    )
    # Ensure holdout is inside series
    settings.yaml.validation.holdout_start = "2024-07-01"
    settings.yaml.validation.walk_forward_folds = 3
    settings.yaml.strategy.min_history_days = 120

    result = run_walk_forward(close, settings)
    assert result.guidance
    payload = result.to_dict()
    assert "honest_disclaimer" in payload
    assert "dsr" in payload
    assert "pbo" in payload
