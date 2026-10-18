"""API integration tests with paper_sim broker."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from trading_bot.api import app as app_module
from trading_bot.brokers.paper_sim import PaperSimBroker
from trading_bot.config.settings import Settings
from trading_bot.services.engine import TradingEngine


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(
        trading_mode="paper",
        data_dir=tmp_path / "d",
        cache_dir=tmp_path / "c",
        model_dir=tmp_path / "m",
        log_dir=tmp_path / "l",
        enable_news_sentiment=False,
        enable_ml_model=False,
        enable_scheduler=False,
    )
    broker = PaperSimBroker(starting_cash=100_000, prices={"SPY": 400, "QQQ": 350})
    engine = TradingEngine(settings, broker=broker)
    monkeypatch.setattr(app_module, "get_settings", lambda: settings)
    monkeypatch.setattr(app_module, "get_engine", lambda: engine)
    monkeypatch.setattr(app_module, "_engine", engine)
    return TestClient(app_module.app)


def test_health_and_dashboard(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    page = client.get("/")
    assert page.status_code == 200
    assert b"Meridian" in page.content


def test_status_and_setup(client: TestClient) -> None:
    s = client.get("/api/status")
    assert s.status_code == 200
    setup = client.get("/api/setup")
    assert setup.status_code == 200
    assert "alpaca" in setup.json()


def test_validation_missing_report(client: TestClient) -> None:
    r = client.get("/api/validation/latest")
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "guidance" in r.json()
