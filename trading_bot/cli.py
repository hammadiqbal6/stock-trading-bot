"""CLI entrypoints."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from trading_bot.config.settings import reload_settings
from trading_bot.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trading-bot", description="AI Stock Trading Bot")
    parser.add_argument("--config", default="config/settings.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run trading engine")
    run_p.add_argument("--once", action="store_true", help="Single cycle")
    run_p.add_argument("--dry-run", action="store_true", help="Do not submit orders")

    sub.add_parser("status", help="Print last/ status snapshot")

    bt = sub.add_parser("backtest", help="Download data and run a simple backtest path")
    bt.add_argument("--start", default="2018-01-01")
    bt.add_argument("--end", default=None)

    val = sub.add_parser("validate", help="Walk-forward + holdout validation report")
    val.add_argument("--start", default="2018-01-01")
    val.add_argument("--end", default=None)
    val.add_argument("--out", default="data/cache/validation_report.json")

    sub.add_parser("setup-check", help="Print onboarding / credentials status")

    args = parser.parse_args(argv)
    settings = reload_settings()
    setup_logging(settings.log_level)

    if args.cmd == "run":
        from trading_bot.services.engine import TradingEngine

        engine = TradingEngine(settings)
        snap = engine.run_once(submit_orders=not args.dry_run)
        print(json.dumps(snap.model_dump(mode="json"), indent=2, default=str))
        return 0 if snap.ok else 1

    if args.cmd == "status":
        from trading_bot.services.engine import TradingEngine

        engine = TradingEngine(settings)
        snap = engine.status()
        print(json.dumps(snap.model_dump(mode="json"), indent=2, default=str))
        return 0

    if args.cmd == "setup-check":
        print(json.dumps(settings.setup_status(), indent=2))
        return 0

    if args.cmd in {"backtest", "validate"}:
        from trading_bot.data.provider import YFinanceProvider
        from trading_bot.validation.walk_forward import run_walk_forward

        symbols = settings.yaml.universe.all_symbols
        provider = YFinanceProvider(cache_dir=settings.cache_dir)
        end = args.end or datetime.now(UTC).strftime("%Y-%m-%d")
        logger.info("downloading_history", symbols=len(symbols), start=args.start, end=end)
        close = provider.get_close_panel(symbols, start=args.start, end=end)
        result = run_walk_forward(close, settings)
        payload = result.to_dict()
        if args.cmd == "validate":
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            print(f"Wrote {out}")
        print(json.dumps(payload, indent=2, default=str))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
