"""Settings and live-trading gate tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from trading_bot.config.settings import Settings, TradingMode


def test_paper_default(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    # use default yaml from repo via absolute path
    s = Settings(
        trading_mode="paper",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        model_dir=tmp_path / "models",
        log_dir=tmp_path / "logs",
    )
    assert s.trading_mode == TradingMode.PAPER
    assert s.alpaca_paper is True
    assert s.yaml.advisory.never_place_orders is True
    assert s.yaml.advisory.never_override_risk is True


def test_live_requires_flags(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    with pytest.raises(ValidationError):
        Settings(
            trading_mode="live",
            live_trading_enabled=False,
            data_dir=tmp_path / "d",
            cache_dir=tmp_path / "c",
            model_dir=tmp_path / "m",
            log_dir=tmp_path / "l",
        )


def test_live_requires_confirm(tmp_path) -> None:
    with pytest.raises(ValidationError):
        Settings(
            trading_mode="live",
            live_trading_enabled=True,
            live_trading_confirm="nope",
            alpaca_paper=False,
            data_dir=tmp_path / "d",
            cache_dir=tmp_path / "c",
            model_dir=tmp_path / "m",
            log_dir=tmp_path / "l",
        )


def test_setup_status_guidance(tmp_path) -> None:
    s = Settings(
        data_dir=tmp_path / "d",
        cache_dir=tmp_path / "c",
        model_dir=tmp_path / "m",
        log_dir=tmp_path / "l",
    )
    status = s.setup_status()
    assert status["alpaca"]["required"] is True
    assert (
        "alpaca.markets" in status["alpaca"]["guidance"].lower()
        or "Alpaca" in status["alpaca"]["guidance"]
    )
    assert status["gdelt"]["configured"] is True
