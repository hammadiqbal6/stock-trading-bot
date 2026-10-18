#!/usr/bin/env python3
"""Run a sample walk-forward validation on a small public ETF universe."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trading_bot.config.settings import get_settings  # noqa: E402
from trading_bot.data.provider import YFinanceProvider  # noqa: E402
from trading_bot.utils.logging import setup_logging  # noqa: E402
from trading_bot.validation.walk_forward import run_walk_forward  # noqa: E402


def main() -> int:
    settings = get_settings()
    setup_logging(settings.log_level)
    symbols = ["SPY", "QQQ", "IWM", "TLT", "GLD", "EFA", "XLE", "AAPL", "MSFT", "JPM"]
    provider = YFinanceProvider(cache_dir=settings.cache_dir)
    end = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"Downloading {symbols} 2019-01-01 → {end} via yfinance…")
    close = provider.get_close_panel(symbols, start="2019-01-01", end=end)
    print(f"Got panel shape={close.shape}")
    result = run_walk_forward(close, settings)
    out = settings.cache_dir / "validation_report.json"
    payload = result.to_dict()
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    print(f"\nWrote {out}")
    print("\nGuidance:", result.guidance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
