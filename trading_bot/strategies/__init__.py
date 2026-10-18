"""Trading strategies."""

from trading_bot.strategies.base import Signal, Strategy, TargetPosition
from trading_bot.strategies.momentum import VolatilityScaledMomentumStrategy

__all__ = [
    "Signal",
    "Strategy",
    "TargetPosition",
    "VolatilityScaledMomentumStrategy",
]
