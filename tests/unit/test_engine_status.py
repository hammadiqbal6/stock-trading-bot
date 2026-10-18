"""TradingEngine status smoke test with paper_sim (no network)."""

from __future__ import annotations

from trading_bot.brokers.paper_sim import PaperSimBroker
from trading_bot.config.settings import Settings
from trading_bot.services.engine import TradingEngine


def test_engine_status_without_prior_run(tmp_path) -> None:
    settings = Settings(
        trading_mode="dry_run",
        data_dir=tmp_path / "d",
        cache_dir=tmp_path / "c",
        model_dir=tmp_path / "m",
        log_dir=tmp_path / "l",
        enable_news_sentiment=False,
        enable_ml_model=False,
    )
    broker = PaperSimBroker(starting_cash=50_000)
    engine = TradingEngine(settings, broker=broker)
    snap = engine.status()
    assert snap.mode == "dry_run"
    assert snap.setup["alpaca"]["required"] is True
    assert "guidance" in snap.model_dump()
