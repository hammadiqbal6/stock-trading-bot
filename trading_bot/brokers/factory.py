"""Broker factory."""

from __future__ import annotations

from trading_bot.brokers.base import Broker
from trading_bot.brokers.ibkr_stub import IBKRBrokerStub
from trading_bot.brokers.paper_sim import PaperSimBroker
from trading_bot.config.settings import BrokerName, Settings, get_settings
from trading_bot.utils.exceptions import ConfigError
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


def get_broker(
    settings: Settings | None = None, *, force: BrokerName | str | None = None
) -> Broker:
    settings = settings or get_settings()
    name = BrokerName(force) if force else settings.yaml.execution.broker

    if name == BrokerName.ALPACA:
        if not settings.has_alpaca_credentials():
            logger.warning(
                "alpaca_credentials_missing_falling_back_to_paper_sim",
                guidance=(
                    "ALPACA_API_KEY/SECRET not set — using in-memory paper_sim. "
                    "Add keys for real Alpaca paper trading."
                ),
            )
            return PaperSimBroker()
        from trading_bot.brokers.alpaca_broker import AlpacaBroker

        return AlpacaBroker(settings)

    if name == BrokerName.PAPER_SIM:
        return PaperSimBroker()

    if name == BrokerName.IBKR:
        return IBKRBrokerStub()

    raise ConfigError(
        f"Unknown broker: {name}",
        guidance="Set execution.broker to alpaca | paper_sim | ibkr in config/settings.yaml",
    )
