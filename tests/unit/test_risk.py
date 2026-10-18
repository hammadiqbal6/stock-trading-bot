"""Risk engine tests."""

from __future__ import annotations

import pytest
from trading_bot.brokers.base import AccountInfo, Position
from trading_bot.config.settings import RiskConfig
from trading_bot.risk.engine import RiskEngine
from trading_bot.strategies.base import TargetPosition
from trading_bot.utils.exceptions import PDTRestrictionError, RiskKillSwitchError


def _acct(equity: float = 100_000, buying_power: float | None = None) -> AccountInfo:
    return AccountInfo(
        equity=equity,
        cash=equity,
        buying_power=buying_power if buying_power is not None else equity,
        portfolio_value=equity,
        paper=True,
    )


def test_kill_switch_on_daily_loss() -> None:
    eng = RiskEngine(RiskConfig(daily_loss_cap_pct=0.02, max_drawdown_pct=0.5))
    eng.state.day_start_equity = 100_000
    eng.state.day_start_date = eng.state.day_start_date  # may be None first
    from datetime import UTC, datetime

    eng.state.day_start_date = datetime.now(UTC).date().isoformat()
    eng.state.day_start_equity = 100_000
    eng.state.peak_equity = 100_000
    eng.update_equity(_acct(97_000))
    assert eng.state.kill_switch is True


def test_position_limit_and_orders() -> None:
    eng = RiskEngine(RiskConfig(max_position_pct=0.1, min_order_notional=1.0))
    decision = eng.build_rebalance_orders(
        account=_acct(),
        positions=[],
        targets=[TargetPosition(symbol="SPY", weight=0.5, reason="test")],
        prices={"SPY": 100.0},
    )
    assert decision.allowed
    assert decision.orders
    # notional capped at 10% of equity = 10k → qty 100
    assert decision.orders[0].qty == pytest.approx(100.0)


def test_pdt_blocks_day_trade() -> None:
    eng = RiskEngine(RiskConfig(pdt_aware=True, min_equity_for_day_trades=25_000))
    with pytest.raises(PDTRestrictionError):
        eng.build_rebalance_orders(
            account=_acct(equity=10_000, buying_power=10_000).model_copy(
                update={"daytrade_count": 3}
            ),
            positions=[],
            targets=[TargetPosition(symbol="AAPL", weight=0.05)],
            prices={"AAPL": 50.0},
            is_day_trade=True,
        )


def test_reset_kill_requires_token() -> None:
    eng = RiskEngine(RiskConfig())
    eng.trip_kill_switch("test")
    with pytest.raises(RiskKillSwitchError):
        eng.reset_kill_switch(confirm="no")
    eng.reset_kill_switch(confirm="RESET_KILL_SWITCH")
    assert eng.state.kill_switch is False


def test_stop_loss_hits() -> None:
    eng = RiskEngine(RiskConfig(stop_loss_pct=0.08))
    hits = eng.stop_loss_hits(
        [
            Position(
                symbol="X",
                qty=1,
                market_value=90,
                avg_entry_price=100,
                current_price=90,
            )
        ]
    )
    assert hits == ["X"]
