"""Trading engine orchestration — paper-first, risk-gated."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from trading_bot.advisory.research_agents import AdvisoryResearchLayer
from trading_bot.brokers.base import Broker, OrderResult
from trading_bot.brokers.factory import get_broker
from trading_bot.config.settings import Settings, TradingMode, get_settings
from trading_bot.data.calendar import MarketCalendar
from trading_bot.data.provider import get_data_provider
from trading_bot.news.aggregator import NewsAggregator
from trading_bot.risk.engine import RiskEngine
from trading_bot.sentiment.pipeline import SentimentPipeline, SentimentResult
from trading_bot.strategies.base import TargetPosition
from trading_bot.strategies.ml_model import WalkForwardML
from trading_bot.strategies.momentum import VolatilityScaledMomentumStrategy
from trading_bot.utils.exceptions import MarketClosedError, TradingBotError
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


class TradingSnapshot(BaseModel):
    ts: datetime
    mode: str
    market: dict[str, Any] = Field(default_factory=dict)
    account: dict[str, Any] = Field(default_factory=dict)
    positions: list[dict[str, Any]] = Field(default_factory=list)
    targets: list[dict[str, Any]] = Field(default_factory=list)
    sentiment: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    orders: list[dict[str, Any]] = Field(default_factory=list)
    advisory: list[dict[str, Any]] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    setup: dict[str, Any] = Field(default_factory=dict)
    ok: bool = True
    guidance: str = ""


class TradingEngine:
    def __init__(self, settings: Settings | None = None, broker: Broker | None = None) -> None:
        self.settings = settings or get_settings()
        self.broker = broker or get_broker(self.settings)
        self.calendar = MarketCalendar()
        self.strategy = VolatilityScaledMomentumStrategy(self.settings.yaml.strategy)
        self.risk = RiskEngine(self.settings.yaml.risk)
        self.news = NewsAggregator(self.settings)
        self.sentiment = SentimentPipeline(self.settings)
        self.ml = WalkForwardML(self.settings.yaml.ml)
        self.advisory = AdvisoryResearchLayer(self.settings)
        self.last_snapshot: TradingSnapshot | None = None
        self._event_log: list[str] = []

    def log(self, msg: str) -> None:
        line = f"{datetime.now(UTC).isoformat()} {msg}"
        self._event_log.append(line)
        self._event_log = self._event_log[-500:]
        logger.info("engine_event", message=msg)

    def run_once(self, *, submit_orders: bool = True) -> TradingSnapshot:
        logs_start = len(self._event_log)
        guidance = ""
        orders_out: list[OrderResult] = []
        targets: list[TargetPosition] = []
        sent_map: dict[str, SentimentResult] = {}
        advisory_reports: list[dict[str, Any]] = []

        session = self.calendar.session_info()
        market = {
            "is_open": session.is_open,
            "is_trading_day": session.is_trading_day,
            "now_et": session.now_et.isoformat(),
            "next_open": session.next_open.isoformat() if session.next_open else None,
            "next_close": session.next_close.isoformat() if session.next_close else None,
            "guidance": session.guidance,
        }

        try:
            account = self.broker.get_account()
            positions = self.broker.list_positions()
            self.risk.update_equity(account)

            symbols = self.settings.yaml.universe.all_symbols
            data = get_data_provider(self.settings, purpose="live")
            end = datetime.now(UTC)
            start = end - timedelta(
                days=max(400, self.settings.yaml.strategy.min_history_days + 40)
            )
            close = data.get_close_panel(symbols, start=start, end=end)
            close.columns = [str(c).upper() for c in close.columns]

            # Sentiment
            if self.settings.yaml.sentiment.enabled:
                arts = self.news.fetch_recent(symbols[:15])  # rate-limit friendly subset
                sent_map = self.sentiment.score_articles(arts)
            sent_scores = {k: v.score for k, v in sent_map.items()}

            ml_scores = self.ml.fit_predict_scores(close) if self.settings.yaml.ml.enabled else {}
            targets = self.strategy.generate_targets(
                close, sentiment=sent_scores, ml_scores=ml_scores
            )
            self.log(f"Generated {len(targets)} targets")

            prices = {
                sym: float(close[sym].dropna().iloc[-1])
                for sym in close.columns
                if not close[sym].dropna().empty
            }
            # Fill missing with broker position prices
            for p in positions:
                prices.setdefault(p.symbol, p.current_price or p.avg_entry_price)

            # Stop-loss exits via risk
            for sym in self.risk.stop_loss_hits(positions):
                self.log(f"Stop-loss hit: {sym}")
                # ensure target weight 0
                targets = [t for t in targets if t.symbol != sym] + [
                    TargetPosition(symbol=sym, weight=0.0, reason="stop_loss")
                ]

            hours_ok = (
                session.is_open or not self.settings.yaml.execution.submit_during_regular_hours_only
            )
            if submit_orders and self.settings.trading_mode in {
                TradingMode.PAPER,
                TradingMode.LIVE,
            }:
                if not hours_ok:
                    guidance = session.guidance
                    self.log("Market closed — skipping order submit")
                    if self.settings.yaml.execution.submit_during_regular_hours_only:
                        raise MarketClosedError(next_open=str(session.next_open))
                decision = self.risk.build_rebalance_orders(
                    account=account,
                    positions=positions,
                    targets=targets,
                    prices=prices,
                    is_day_trade=False,  # weekly rebalance → typically not day trades
                )
                guidance = decision.guidance
                if decision.allowed:
                    for order in decision.orders:
                        if self.settings.trading_mode == TradingMode.DRY_RUN:
                            self.log(f"DRY_RUN order {order.side} {order.symbol}")
                            continue
                        result = self.broker.submit_order(order)
                        orders_out.append(result)
                        self.log(
                            f"Submitted {result.side} {result.symbol} qty={result.qty} "
                            f"status={result.status}"
                        )
                else:
                    self.log(f"Risk blocked orders: {decision.guidance}")
            elif self.settings.trading_mode == TradingMode.BACKTEST:
                guidance = "Backtest mode — no live orders."
            else:
                # dry run default path
                decision = self.risk.build_rebalance_orders(
                    account=account,
                    positions=positions,
                    targets=targets,
                    prices=prices,
                )
                guidance = (
                    f"Dry-run: would submit {len(decision.orders)} orders. {decision.guidance}"
                )

            # Advisory (never affects orders)
            if self.advisory.enabled:
                for t in targets[:5]:
                    report = self.advisory.analyze(
                        t.symbol,
                        headlines=sent_map.get(t.symbol).headlines if t.symbol in sent_map else [],
                        technical_summary=t.reason,
                        risk_summary=self.risk.state.kill_reason or "within limits",
                    )
                    advisory_reports.append(report.model_dump())

            ok = True
        except MarketClosedError as exc:
            ok = True
            guidance = exc.guidance
            self.log(exc.message)
            try:
                account = self.broker.get_account()
                positions = self.broker.list_positions()
            except Exception:
                account = None
                positions = []
        except TradingBotError as exc:
            ok = False
            guidance = exc.guidance
            self.log(f"ERROR {exc.code}: {exc.message}")
            try:
                account = self.broker.get_account()
                positions = self.broker.list_positions()
            except Exception:
                account = None
                positions = []
        except Exception as exc:
            ok = False
            guidance = f"Unexpected error: {exc}. Check logs and Setup wizard."
            self.log(f"UNEXPECTED {exc}")
            account = None
            positions = []

        snap = TradingSnapshot(
            ts=datetime.now(UTC),
            mode=self.settings.trading_mode.value,
            market=market,
            account=account.model_dump() if account else {},
            positions=[p.model_dump() for p in positions] if positions else [],
            targets=[t.model_dump() for t in targets],
            sentiment={k: v.model_dump() for k, v in sent_map.items()},
            risk=self.risk.snapshot(),
            orders=[o.model_dump(mode="json") for o in orders_out],
            advisory=advisory_reports,
            logs=self._event_log[logs_start:],
            setup=self.settings.setup_status(),
            ok=ok,
            guidance=guidance or "Cycle complete.",
        )
        self.last_snapshot = snap
        return snap

    def status(self) -> TradingSnapshot:
        session = self.calendar.session_info()
        market = {
            "is_open": session.is_open,
            "is_trading_day": session.is_trading_day,
            "now_et": session.now_et.isoformat(),
            "next_open": session.next_open.isoformat() if session.next_open else None,
            "next_close": session.next_close.isoformat() if session.next_close else None,
            "guidance": session.guidance,
        }
        account_dict: dict[str, Any] = {}
        positions_list: list[dict[str, Any]] = []
        try:
            account = self.broker.get_account()
            positions = self.broker.list_positions()
            self.risk.update_equity(account)
            account_dict = account.model_dump()
            positions_list = [p.model_dump() for p in positions]
        except Exception as exc:
            guidance = f"Status refresh issue: {exc}"
            if self.last_snapshot:
                self.last_snapshot.guidance = guidance
                self.last_snapshot.market = {**self.last_snapshot.market, **market}
                return self.last_snapshot
            return TradingSnapshot(
                ts=datetime.now(UTC),
                mode=self.settings.trading_mode.value,
                market=market,
                setup=self.settings.setup_status(),
                risk=self.risk.snapshot(),
                guidance=guidance,
                logs=self._event_log[-50:],
                ok=False,
            )

        if self.last_snapshot:
            self.last_snapshot.account = account_dict
            self.last_snapshot.positions = positions_list
            self.last_snapshot.risk = self.risk.snapshot()
            self.last_snapshot.market = {**self.last_snapshot.market, **market}
            self.last_snapshot.setup = self.settings.setup_status()
            return self.last_snapshot

        return TradingSnapshot(
            ts=datetime.now(UTC),
            mode=self.settings.trading_mode.value,
            market=market,
            account=account_dict,
            positions=positions_list,
            setup=self.settings.setup_status(),
            risk=self.risk.snapshot(),
            guidance="No cycle run yet — use Run Once or wait for scheduler.",
            logs=self._event_log[-50:],
        )
