"""Strategy interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

import pandas as pd
from pydantic import BaseModel, Field


class SignalSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    BLOCK = "block"


class Signal(BaseModel):
    symbol: str
    side: SignalSide
    strength: float = 0.0  # -1..1
    target_weight: float = 0.0
    reason: str = ""
    metadata: dict[str, float | str | bool] = Field(default_factory=dict)


class TargetPosition(BaseModel):
    symbol: str
    weight: float
    reason: str = ""
    blocked: bool = False
    block_reason: str = ""
    sentiment_score: float | None = None
    metadata: dict[str, float | str | bool] = Field(default_factory=dict)


class Strategy(ABC):
    name: str

    @abstractmethod
    def generate_targets(
        self,
        close: pd.DataFrame,
        *,
        as_of: pd.Timestamp | None = None,
        sentiment: dict[str, float] | None = None,
        ml_scores: dict[str, float] | None = None,
    ) -> list[TargetPosition]:
        """Produce target portfolio weights summing roughly to <= 1."""
        ...
