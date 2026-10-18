"""Calendar, rate limiter, and broker factory coverage."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from trading_bot.brokers.factory import get_broker
from trading_bot.brokers.ibkr_stub import IBKRBrokerStub
from trading_bot.brokers.paper_sim import PaperSimBroker
from trading_bot.config.settings import BrokerName, Settings
from trading_bot.data.calendar import MarketCalendar
from trading_bot.utils.exceptions import BrokerError
from trading_bot.utils.rate_limit import RateLimitError, RateLimiter


def test_calendar_session_info() -> None:
    cal = MarketCalendar()
    info = cal.session_info()
    assert info.now_et.tzinfo is not None
    assert info.guidance
    # deterministic weekday check
    monday = datetime(2024, 6, 3, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    assert cal.is_trading_day(monday.date()) is True


def test_rate_limiter_nonblocking() -> None:
    lim = RateLimiter(rate=0.01, capacity=1, name="test")
    lim.acquire(1)
    with pytest.raises(RateLimitError):
        lim.acquire(1, block=False)


def test_factory_paper_sim_and_ibkr(tmp_path) -> None:
    settings = Settings(
        trading_mode="paper",
        data_dir=tmp_path / "d",
        cache_dir=tmp_path / "c",
        model_dir=tmp_path / "m",
        log_dir=tmp_path / "l",
    )
    b = get_broker(settings, force=BrokerName.PAPER_SIM)
    assert isinstance(b, PaperSimBroker)
    assert b.health_check()["ok"] is True

    ibkr = get_broker(settings, force=BrokerName.IBKR)
    assert isinstance(ibkr, IBKRBrokerStub)
    assert ibkr.health_check()["implemented"] is False
    with pytest.raises(BrokerError):
        ibkr.get_account()
