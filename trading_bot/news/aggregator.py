"""Combine Finnhub + GDELT with graceful degradation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from trading_bot.config.settings import Settings, get_settings
from trading_bot.news.base import NewsArticle, NewsSource
from trading_bot.news.gdelt_source import GDELTNewsSource
from trading_bot.utils.exceptions import MissingCredentialsError
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


class NewsAggregator:
    def __init__(self, settings: Settings | None = None, sources: list[NewsSource] | None = None):
        self.settings = settings or get_settings()
        if sources is not None:
            self.sources = sources
        else:
            self.sources = self._default_sources()

    def _default_sources(self) -> list[NewsSource]:
        sources: list[NewsSource] = [GDELTNewsSource()]
        try:
            from trading_bot.news.finnhub_source import FinnhubNewsSource

            sources.insert(0, FinnhubNewsSource(self.settings))
        except MissingCredentialsError as exc:
            logger.info("finnhub_skipped", guidance=exc.guidance)
        return sources

    def fetch_recent(
        self,
        symbols: list[str],
        *,
        lookback_hours: int | None = None,
        limit_per_source: int = 30,
    ) -> list[NewsArticle]:
        hours = lookback_hours or self.settings.yaml.sentiment.lookback_hours
        since = datetime.now(UTC) - timedelta(hours=hours)
        all_arts: list[NewsArticle] = []
        for src in self.sources:
            try:
                arts = src.fetch(symbols, since=since, limit=limit_per_source)
                all_arts.extend(arts)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "news_source_failed",
                    source=src.name,
                    error=str(exc),
                    guidance="Continuing with remaining news sources.",
                )
        # de-dupe by headline+symbol
        seen: set[str] = set()
        unique: list[NewsArticle] = []
        for a in sorted(
            all_arts,
            key=lambda x: x.published_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        ):
            key = f"{a.symbol}:{a.headline.strip().lower()}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(a)
        return unique

    def health_check(self) -> dict[str, Any]:
        return {
            "sources": [s.health_check() for s in self.sources],
            "guidance": "At least GDELT should work without keys; Finnhub optional.",
        }
