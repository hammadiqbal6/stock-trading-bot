"""Hard risk rules — LLM and advisory layers must never override these."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, Field

from trading_bot.brokers.base import AccountInfo, OrderRequest, OrderSide, Position
from trading_bot.config.settings import RiskConfig
from trading_bot.strategies.base import TargetPosition
from trading_bot.utils.exceptions import PDTRestrictionError, RiskKillSwitchError
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


class RiskState(BaseModel):
    kill_switch: bool = False
    kill_reason: str = ""
    day_start_equity: float | None = None
    day_start_date: str | None = None
    peak_equity: float | None = None
    daily_pnl_pct: float = 0.0
    drawdown_pct: float = 0.0
    day_trades_today: int = 0
    messages: list[str] = Field(default_factory=list)


class RiskDecision(BaseModel):
    allowed: bool
    orders: list[OrderRequest] = Field(default_factory=list)
    rejected: list[dict[str, str]] = Field(default_factory=list)
    state: RiskState
    guidance: str = ""


@dataclass
class RiskEngine:
    """Enforces position limits, daily loss cap, max DD kill switch, PDT awareness."""

    config: RiskConfig
    state: RiskState = field(default_factory=RiskState)

    def update_equity(self, account: AccountInfo) -> RiskState:
        today = datetime.now(UTC).date().isoformat()
        eq = account.equity
        if self.state.day_start_date != today or self.state.day_start_equity is None:
            self.state.day_start_date = today
            self.state.day_start_equity = eq
            self.state.day_trades_today = 0
        if self.state.peak_equity is None or eq > self.state.peak_equity:
            self.state.peak_equity = eq

        start = self.state.day_start_equity or eq
        peak = self.state.peak_equity or eq
        self.state.daily_pnl_pct = (eq - start) / start if start else 0.0
        self.state.drawdown_pct = (peak - eq) / peak if peak else 0.0

        if self.config.kill_switch_enabled and not self.state.kill_switch:
            if self.state.daily_pnl_pct <= -abs(self.config.daily_loss_cap_pct):
                self.trip_kill_switch(
                    f"Daily loss {self.state.daily_pnl_pct:.2%} breached cap "
                    f"{self.config.daily_loss_cap_pct:.2%}"
                )
            if self.state.drawdown_pct >= abs(self.config.max_drawdown_pct):
                self.trip_kill_switch(
                    f"Drawdown {self.state.drawdown_pct:.2%} breached max "
                    f"{self.config.max_drawdown_pct:.2%}"
                )
        return self.state

    def trip_kill_switch(self, reason: str) -> None:
        self.state.kill_switch = True
        self.state.kill_reason = reason
        self.state.messages.append(reason)
        logger.error("kill_switch_tripped", reason=reason)

    def reset_kill_switch(self, *, confirm: str) -> None:
        if confirm != "RESET_KILL_SWITCH":
            raise RiskKillSwitchError("Reset denied — pass confirm=RESET_KILL_SWITCH")
        self.state.kill_switch = False
        self.state.kill_reason = ""
        self.state.messages.append("Kill switch manually reset")

    def build_rebalance_orders(
        self,
        *,
        account: AccountInfo,
        positions: list[Position],
        targets: list[TargetPosition],
        prices: dict[str, float],
        is_day_trade: bool = False,
    ) -> RiskDecision:
        self.update_equity(account)
        rejected: list[dict[str, str]] = []

        if self.state.kill_switch:
            return RiskDecision(
                allowed=False,
                orders=[],
                rejected=[{"symbol": "*", "reason": self.state.kill_reason}],
                state=self.state,
                guidance=(
                    f"Kill switch active: {self.state.kill_reason}. "
                    "No new orders. Inspect Risk panel; reset only after review."
                ),
            )

        if account.trading_blocked or account.account_blocked:
            return RiskDecision(
                allowed=False,
                state=self.state,
                guidance="Broker reports trading/account blocked. Check Alpaca dashboard.",
            )

        # PDT awareness
        if (
            self.config.pdt_aware
            and is_day_trade
            and account.equity < self.config.min_equity_for_day_trades
            and (account.daytrade_count >= 3 or self.state.day_trades_today >= 3)
        ):
            raise PDTRestrictionError(account.daytrade_count, account.equity)

        pos_map = {p.symbol: p for p in positions}
        target_map = {t.symbol: t for t in targets if not t.blocked}
        for t in targets:
            if t.blocked:
                rejected.append({"symbol": t.symbol, "reason": t.block_reason or "blocked"})

        equity = max(account.equity, 1.0)
        max_pos_value = equity * self.config.max_position_pct

        # Desired notional per symbol
        desired: dict[str, float] = {}
        for sym, t in target_map.items():
            notional = min(t.weight * equity, max_pos_value)
            if notional < self.config.min_order_notional and t.weight > 0:
                rejected.append(
                    {
                        "symbol": sym,
                        "reason": (
                            f"Target notional ${notional:.2f} below minimum "
                            f"${self.config.min_order_notional:.2f}"
                        ),
                    }
                )
                continue
            desired[sym] = notional

        # Close names no longer targeted
        for sym, pos in pos_map.items():
            if sym not in desired and abs(pos.qty) > 0:
                desired[sym] = 0.0

        orders: list[OrderRequest] = []
        gross = 0.0
        for sym, target_notional in desired.items():
            price = prices.get(sym)
            if price is None or price <= 0:
                rejected.append(
                    {
                        "symbol": sym,
                        "reason": "No price available — cannot size order. Check data feed.",
                    }
                )
                continue
            current_qty = pos_map[sym].qty if sym in pos_map else 0.0
            current_notional = current_qty * price
            delta = target_notional - current_notional
            if abs(delta) < self.config.min_order_notional:
                continue

            if delta > 0:
                # buy
                if is_day_trade and self.config.pdt_aware:
                    self._check_pdt(account)
                qty = delta / price
                if not self.config.fractional_shares:
                    qty = float(int(qty))
                    if qty <= 0:
                        continue
                    delta = qty * price
                if delta > account.buying_power + 1e-6:
                    rejected.append(
                        {
                            "symbol": sym,
                            "reason": (
                                f"Insufficient buying power for ${delta:.2f} "
                                f"(available ${account.buying_power:.2f})"
                            ),
                        }
                    )
                    continue
                gross += target_notional
                orders.append(
                    OrderRequest(
                        symbol=sym,
                        side=OrderSide.BUY,
                        qty=qty if self.config.fractional_shares else qty,
                        notional=None,
                        fractional=self.config.fractional_shares,
                    )
                )
            else:
                # sell
                sell_notional = abs(delta)
                qty = min(abs(current_qty), sell_notional / price)
                if not self.config.fractional_shares:
                    qty = float(int(qty))
                    if qty <= 0:
                        continue
                if is_day_trade and self.config.pdt_aware:
                    self._check_pdt(account)
                orders.append(
                    OrderRequest(
                        symbol=sym,
                        side=OrderSide.SELL,
                        qty=qty,
                        fractional=self.config.fractional_shares,
                    )
                )

        if gross / equity > self.config.max_gross_exposure + 1e-9:
            return RiskDecision(
                allowed=False,
                orders=[],
                rejected=rejected
                + [
                    {
                        "symbol": "*",
                        "reason": (
                            f"Gross exposure {gross / equity:.2%} exceeds "
                            f"{self.config.max_gross_exposure:.2%}"
                        ),
                    }
                ],
                state=self.state,
                guidance="Reduce target weights or max_position_pct.",
            )

        guidance = "Orders passed risk checks."
        if rejected:
            guidance = f"{len(rejected)} symbol(s) rejected — see details; others may proceed."
        if not orders:
            guidance = "No rebalance orders needed (or all rejected)."

        return RiskDecision(
            allowed=True,
            orders=orders,
            rejected=rejected,
            state=self.state,
            guidance=guidance,
        )

    def stop_loss_hits(self, positions: list[Position]) -> list[str]:
        hits: list[str] = []
        thr = -abs(self.config.stop_loss_pct)
        for p in positions:
            if p.avg_entry_price <= 0:
                continue
            pnl_pct = (p.current_price - p.avg_entry_price) / p.avg_entry_price
            if pnl_pct <= thr:
                hits.append(p.symbol)
        return hits

    def _check_pdt(self, account: AccountInfo) -> None:
        if account.equity >= self.config.min_equity_for_day_trades:
            return
        used = max(account.daytrade_count, self.state.day_trades_today)
        if used >= 3:
            raise PDTRestrictionError(used, account.equity)
        self.state.day_trades_today += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "kill_switch": self.state.kill_switch,
            "kill_reason": self.state.kill_reason,
            "daily_pnl_pct": self.state.daily_pnl_pct,
            "drawdown_pct": self.state.drawdown_pct,
            "day_trades_today": self.state.day_trades_today,
            "limits": self.config.model_dump(),
            "guidance": (
                self.state.kill_reason
                if self.state.kill_switch
                else "Risk engine armed; hard limits cannot be overridden by LLM/advisory."
            ),
        }
