"""Interactive Brokers (IBKR) stub — reserved for future live trading.

IBKR accepts customers from Pakistan for real-money trading. This module
documents the intended interface and raises NotImplementedError until wired
with ib_insync / ibapi.

See docs/architecture/brokers.md and docs/decisions/0002-broker-abstraction.md.
"""

from __future__ import annotations

from typing import Any

from trading_bot.brokers.base import (
    AccountInfo,
    Broker,
    OrderRequest,
    OrderResult,
    Position,
)
from trading_bot.utils.exceptions import BrokerError


class IBKRBrokerStub(Broker):
    """Placeholder adapter — does not place orders."""

    name = "ibkr"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._args = args
        self._kwargs = kwargs

    def _nyi(self) -> None:
        raise BrokerError(
            "IBKR broker is not implemented yet (stub only)",
            guidance=(
                "Use Alpaca paper trading for now (default). "
                "IBKR is planned for live trading in markets where Alpaca "
                "does not accept the account holder (e.g. Pakistan for real money). "
                "Track progress in docs/roadmap.md. To contribute, implement "
                "trading_bot/brokers/ibkr_broker.py against the Broker ABC and "
                "register it in trading_bot/brokers/factory.py."
            ),
        )

    def get_account(self) -> AccountInfo:
        self._nyi()
        raise AssertionError("unreachable")

    def list_positions(self) -> list[Position]:
        self._nyi()
        raise AssertionError("unreachable")

    def submit_order(self, order: OrderRequest) -> OrderResult:
        self._nyi()
        raise AssertionError("unreachable")

    def cancel_order(self, order_id: str) -> None:
        self._nyi()

    def get_order(self, order_id: str) -> OrderResult:
        self._nyi()
        raise AssertionError("unreachable")

    def list_orders(self, status: str = "open") -> list[OrderResult]:
        self._nyi()
        raise AssertionError("unreachable")

    def health_check(self) -> dict[str, Any]:
        return {
            "ok": False,
            "broker": self.name,
            "implemented": False,
            "guidance": (
                "IBKR stub only. Switch execution.broker to 'alpaca' or 'paper_sim' "
                "in config/settings.yaml."
            ),
        }
