"""Alpaca broker adapter (paper by default via paper-api.alpaca.markets)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from trading_bot.brokers.base import (
    AccountInfo,
    Broker,
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderStatus,
    Position,
)
from trading_bot.config.settings import Settings
from trading_bot.utils.exceptions import BrokerError, MissingCredentialsError, TradingBotError
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)

_STATUS_MAP = {
    "new": OrderStatus.NEW,
    "accepted": OrderStatus.ACCEPTED,
    "pending_new": OrderStatus.PENDING,
    "accepted_for_bidding": OrderStatus.ACCEPTED,
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    "filled": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELED,
    "cancelled": OrderStatus.CANCELED,
    "expired": OrderStatus.EXPIRED,
    "replaced": OrderStatus.CANCELED,
    "pending_cancel": OrderStatus.PENDING,
    "pending_replace": OrderStatus.PENDING,
    "rejected": OrderStatus.REJECTED,
    "suspended": OrderStatus.REJECTED,
    "calculated": OrderStatus.ACCEPTED,
}


class AlpacaBroker(Broker):
    name = "alpaca"

    def __init__(self, settings: Settings) -> None:
        if not settings.has_alpaca_credentials():
            raise MissingCredentialsError(
                "Alpaca",
                guidance=(
                    "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env. "
                    "Create a free paper account at https://app.alpaca.markets/signup "
                    "(open worldwide, including Pakistan). Paper trading uses "
                    "https://paper-api.alpaca.markets."
                ),
            )
        self._settings = settings
        self._paper = settings.alpaca_paper or settings.trading_mode.value != "live"
        try:
            from alpaca.trading.client import TradingClient
        except ImportError as exc:
            raise BrokerError(
                "alpaca-py is not installed",
                guidance="Run: pip install -e .  (alpaca-py is a core dependency)",
            ) from exc

        self._client = TradingClient(
            api_key=settings.alpaca_api_key.get_secret_value(),
            secret_key=settings.alpaca_secret_key.get_secret_value(),
            paper=self._paper,
        )
        logger.info("alpaca_broker_initialized", paper=self._paper)

    def get_account(self) -> AccountInfo:
        try:
            acct = self._client.get_account()
        except Exception as exc:
            raise BrokerError(
                f"Failed to fetch Alpaca account: {exc}",
                guidance=(
                    "Verify API keys, network access to paper-api.alpaca.markets, "
                    "and that the account is not locked. Check Alpaca status page if outages persist."
                ),
            ) from exc
        return AccountInfo(
            equity=float(acct.equity or 0),
            cash=float(acct.cash or 0),
            buying_power=float(acct.buying_power or 0),
            portfolio_value=float(acct.portfolio_value or 0),
            currency=str(acct.currency or "USD"),
            pattern_day_trader=bool(acct.pattern_day_trader),
            daytrade_count=int(acct.daytrade_count or 0),
            trading_blocked=bool(acct.trading_blocked),
            account_blocked=bool(acct.account_blocked),
            paper=self._paper,
            raw=acct.model_dump() if hasattr(acct, "model_dump") else {},
        )

    def list_positions(self) -> list[Position]:
        try:
            positions = self._client.get_all_positions()
        except Exception as exc:
            raise BrokerError(
                f"Failed to list positions: {exc}",
                guidance="Check Alpaca connectivity and credentials.",
            ) from exc
        out: list[Position] = []
        for p in positions:
            out.append(
                Position(
                    symbol=str(p.symbol),
                    qty=float(p.qty),
                    market_value=float(p.market_value or 0),
                    avg_entry_price=float(p.avg_entry_price or 0),
                    unrealized_pl=float(p.unrealized_pl or 0),
                    current_price=float(p.current_price or 0),
                    side=str(p.side or "long"),
                )
            )
        return out

    def submit_order(self, order: OrderRequest) -> OrderResult:
        from alpaca.trading.enums import OrderSide as AlpacaSide
        from alpaca.trading.enums import TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

        side = AlpacaSide.BUY if order.side == OrderSide.BUY else AlpacaSide.SELL
        tif_map = {"day": TimeInForce.DAY, "gtc": TimeInForce.GTC, "ioc": TimeInForce.IOC}
        tif = tif_map.get(order.time_in_force.lower(), TimeInForce.DAY)

        try:
            if order.order_type == "limit" and order.limit_price is not None:
                req = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    notional=order.notional if order.qty is None else None,
                    side=side,
                    time_in_force=tif,
                    limit_price=order.limit_price,
                    client_order_id=order.client_order_id,
                )
            else:
                req = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    notional=order.notional if order.qty is None else None,
                    side=side,
                    time_in_force=tif,
                    client_order_id=order.client_order_id,
                )
            result = self._client.submit_order(req)
        except Exception as exc:
            raise BrokerError(
                f"Order rejected/failed for {order.symbol}: {exc}",
                guidance=(
                    "Common causes: market closed, insufficient buying power, "
                    "invalid qty/notional, or symbol not tradable on Alpaca. "
                    "Check the Risk panel and Market Hours indicator."
                ),
            ) from exc

        return self._map_order(result)

    def cancel_order(self, order_id: str) -> None:
        try:
            self._client.cancel_order_by_id(order_id)
        except Exception as exc:
            raise BrokerError(
                f"Failed to cancel order {order_id}: {exc}",
                guidance="Order may already be filled or canceled. Refresh orders list.",
            ) from exc

    def get_order(self, order_id: str) -> OrderResult:
        try:
            result = self._client.get_order_by_id(order_id)
        except Exception as exc:
            raise BrokerError(f"Failed to get order {order_id}: {exc}") from exc
        return self._map_order(result)

    def list_orders(self, status: str = "open") -> list[OrderResult]:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        status_map = {
            "open": QueryOrderStatus.OPEN,
            "closed": QueryOrderStatus.CLOSED,
            "all": QueryOrderStatus.ALL,
        }
        req = GetOrdersRequest(status=status_map.get(status, QueryOrderStatus.OPEN), limit=100)
        try:
            orders = self._client.get_orders(req)
        except Exception as exc:
            raise BrokerError(f"Failed to list orders: {exc}") from exc
        return [self._map_order(o) for o in orders]

    def health_check(self) -> dict[str, Any]:
        try:
            acct = self.get_account()
            return {
                "ok": True,
                "broker": self.name,
                "paper": self._paper,
                "equity": acct.equity,
                "trading_blocked": acct.trading_blocked,
                "guidance": "Alpaca connection healthy.",
            }
        except TradingBotError as exc:
            return {
                "ok": False,
                "broker": self.name,
                "guidance": exc.guidance,
                "error": exc.message,
            }
        except Exception as exc:
            return {
                "ok": False,
                "broker": self.name,
                "error": str(exc),
                "guidance": (
                    "Cannot reach Alpaca. Check network, keys, and "
                    "https://app.alpaca.markets/paper/dashboard/overview"
                ),
            }

    def _map_order(self, result: Any) -> OrderResult:
        status_raw = str(getattr(result, "status", "pending")).lower()
        side_raw = str(getattr(result, "side", "buy")).lower()
        submitted = getattr(result, "submitted_at", None)
        if submitted is not None and submitted.tzinfo is None:
            submitted = submitted.replace(tzinfo=UTC)
        return OrderResult(
            id=str(result.id),
            client_order_id=getattr(result, "client_order_id", None),
            symbol=str(result.symbol),
            side=OrderSide.BUY if side_raw == "buy" else OrderSide.SELL,
            qty=float(result.qty or 0),
            filled_qty=float(result.filled_qty or 0),
            filled_avg_price=(
                float(result.filled_avg_price) if result.filled_avg_price is not None else None
            ),
            status=_STATUS_MAP.get(status_raw, OrderStatus.PENDING),
            submitted_at=submitted if isinstance(submitted, datetime) else None,
            raw=result.model_dump() if hasattr(result, "model_dump") else {},
        )
