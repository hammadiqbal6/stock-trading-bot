"""Paper simulator broker tests."""

from __future__ import annotations

import pytest
from trading_bot.brokers.base import OrderRequest, OrderSide
from trading_bot.brokers.paper_sim import PaperSimBroker
from trading_bot.utils.exceptions import InsufficientBuyingPowerError


def test_buy_sell_roundtrip() -> None:
    b = PaperSimBroker(starting_cash=10_000, prices={"SPY": 100})
    r = b.submit_order(OrderRequest(symbol="SPY", side=OrderSide.BUY, qty=10))
    assert r.filled_qty == 10
    assert b.cash == pytest.approx(9000)
    pos = b.list_positions()
    assert len(pos) == 1
    b.submit_order(OrderRequest(symbol="SPY", side=OrderSide.SELL, qty=10))
    assert b.list_positions() == []
    assert b.cash == pytest.approx(10_000)


def test_insufficient_buying_power() -> None:
    b = PaperSimBroker(starting_cash=100, prices={"AAPL": 200})
    with pytest.raises(InsufficientBuyingPowerError):
        b.submit_order(OrderRequest(symbol="AAPL", side=OrderSide.BUY, qty=1))
