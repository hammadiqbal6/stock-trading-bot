"""News source interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    id: str
    symbol: str | None = None
    headline: str
    summary: str = ""
    source: str
    url: str = ""
    published_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class NewsSource(ABC):
    name: str

    @abstractmethod
    def fetch(
        self,
        symbols: list[str],
        *,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsArticle]: ...

    @abstractmethod
    def health_check(self) -> dict[str, Any]: ...
