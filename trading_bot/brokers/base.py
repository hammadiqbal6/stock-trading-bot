"""Abstract broker interface — Alpaca today, IBKR later."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    NEW = "new"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    PENDING = "pending"
    EXPIRED = "expired"


class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    qty: float | None = None
    notional: float | None = None
    order_type: str = "market"
    time_in_force: str = "day"
    limit_price: float | None = None
    client_order_id: str | None = None
    fractional: bool = True

    def model_post_init(self, __context: Any) -> None:
        if self.qty is None and self.notional is None:
            msg = "OrderRequest requires qty or notional"
            raise ValueError(msg)
        self.symbol = self.symbol.upper().strip()


class OrderResult(BaseModel):
    id: str
    client_order_id: str | None = None
    symbol: str
    side: OrderSide
    qty: float = 0.0
    filled_qty: float = 0.0
    filled_avg_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    submitted_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


class Position(BaseModel):
    symbol: str
    qty: float
    market_value: float
    avg_entry_price: float
    unrealized_pl: float = 0.0
    current_price: float = 0.0
    side: str = "long"


class AccountInfo(BaseModel):
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    currency: str = "USD"
    pattern_day_trader: bool = False
    daytrade_count: int = 0
    trading_blocked: bool = False
    account_blocked: bool = False
    paper: bool = True
    raw: dict[str, Any] = Field(default_factory=dict)


class Broker(ABC):
    """Broker adapter contract.

    Implementations must never silently place live orders when configured for paper.
    """

    name: str

    @abstractmethod
    def get_account(self) -> AccountInfo:
        ...

    @abstractmethod
    def list_positions(self) -> list[Position]:
        ...

    @abstractmethod
    def submit_order(self, order: OrderRequest) -> OrderResult:
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> None:
        ...

    @abstractmethod
    def get_order(self, order_id: str) -> OrderResult:
        ...

    @abstractmethod
    def list_orders(self, status: str = "open") -> list[OrderResult]:
        ...

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return status + actionable guidance on failure."""
        ...

    def close_position(self, symbol: str) -> OrderResult | None:
        positions = {p.symbol: p for p in self.list_positions()}
        pos = positions.get(symbol.upper())
        if not pos or abs(pos.qty) < 1e-9:
            return None
        side = OrderSide.SELL if pos.qty > 0 else OrderSide.BUY
        return self.submit_order(
            OrderRequest(symbol=symbol, side=side, qty=abs(pos.qty), fractional=True)
        )
