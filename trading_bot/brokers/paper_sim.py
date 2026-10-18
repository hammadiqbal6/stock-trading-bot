"""In-memory paper broker for local demos and tests without Alpaca keys."""

from __future__ import annotations

import uuid
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
from trading_bot.utils.exceptions import InsufficientBuyingPowerError


class PaperSimBroker(Broker):
    name = "paper_sim"

    def __init__(
        self,
        *,
        starting_cash: float = 100_000.0,
        prices: dict[str, float] | None = None,
    ) -> None:
        self.cash = starting_cash
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, OrderResult] = {}
        self._prices = prices or {}
        self.daytrade_count = 0

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol.upper()] = price
        if symbol.upper() in self._positions:
            pos = self._positions[symbol.upper()]
            mv = pos.qty * price
            self._positions[symbol.upper()] = pos.model_copy(
                update={
                    "current_price": price,
                    "market_value": mv,
                    "unrealized_pl": (price - pos.avg_entry_price) * pos.qty,
                }
            )

    def get_account(self) -> AccountInfo:
        positions_value = sum(p.market_value for p in self._positions.values())
        equity = self.cash + positions_value
        return AccountInfo(
            equity=equity,
            cash=self.cash,
            buying_power=self.cash,
            portfolio_value=equity,
            pattern_day_trader=False,
            daytrade_count=self.daytrade_count,
            paper=True,
        )

    def list_positions(self) -> list[Position]:
        return list(self._positions.values())

    def submit_order(self, order: OrderRequest) -> OrderResult:
        price = self._prices.get(order.symbol, 100.0)
        if order.qty is not None:
            qty = float(order.qty)
            notional = qty * price
        else:
            assert order.notional is not None
            notional = float(order.notional)
            qty = notional / price if price else 0.0

        if order.side == OrderSide.BUY and notional > self.cash + 1e-6:
            raise InsufficientBuyingPowerError(notional, self.cash)

        if order.side == OrderSide.BUY:
            self.cash -= notional
            existing = self._positions.get(order.symbol)
            if existing:
                new_qty = existing.qty + qty
                avg = (
                    (existing.avg_entry_price * existing.qty + price * qty) / new_qty
                    if new_qty
                    else price
                )
            else:
                new_qty = qty
                avg = price
            self._positions[order.symbol] = Position(
                symbol=order.symbol,
                qty=new_qty,
                market_value=new_qty * price,
                avg_entry_price=avg,
                current_price=price,
                unrealized_pl=(price - avg) * new_qty,
            )
        else:
            existing = self._positions.get(order.symbol)
            held = existing.qty if existing else 0.0
            sell_qty = min(qty, held)
            self.cash += sell_qty * price
            remaining = held - sell_qty
            if remaining <= 1e-9:
                self._positions.pop(order.symbol, None)
            elif existing:
                self._positions[order.symbol] = existing.model_copy(
                    update={
                        "qty": remaining,
                        "market_value": remaining * price,
                        "unrealized_pl": (price - existing.avg_entry_price) * remaining,
                        "current_price": price,
                    }
                )

        result = OrderResult(
            id=str(uuid.uuid4()),
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            qty=qty,
            filled_qty=qty,
            filled_avg_price=price,
            status=OrderStatus.FILLED,
            submitted_at=datetime.now(UTC),
            message="paper_sim fill",
        )
        self._orders[result.id] = result
        return result

    def cancel_order(self, order_id: str) -> None:
        if order_id in self._orders:
            o = self._orders[order_id]
            self._orders[order_id] = o.model_copy(update={"status": OrderStatus.CANCELED})

    def get_order(self, order_id: str) -> OrderResult:
        return self._orders[order_id]

    def list_orders(self, status: str = "open") -> list[OrderResult]:
        orders = list(self._orders.values())
        if status == "open":
            return [o for o in orders if o.status in {OrderStatus.NEW, OrderStatus.PENDING}]
        if status == "closed":
            return [
                o
                for o in orders
                if o.status in {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}
            ]
        return orders

    def health_check(self) -> dict[str, Any]:
        acct = self.get_account()
        return {
            "ok": True,
            "broker": self.name,
            "paper": True,
            "equity": acct.equity,
            "guidance": "In-memory paper simulator is healthy (no external broker).",
        }
