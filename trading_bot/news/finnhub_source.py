"""Finnhub free company news (60/min)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from trading_bot.config.settings import Settings
from trading_bot.news.base import NewsArticle, NewsSource
from trading_bot.utils.exceptions import MissingCredentialsError
from trading_bot.utils.logging import get_logger
from trading_bot.utils.rate_limit import RateLimiter

logger = get_logger(__name__)


class FinnhubNewsSource(NewsSource):
    name = "finnhub"
    BASE = "https://finnhub.io/api/v1"

    def __init__(self, settings: Settings) -> None:
        if not settings.has_finnhub():
            raise MissingCredentialsError(
                "Finnhub",
                guidance=(
                    "Optional: set FINNHUB_API_KEY from https://finnhub.io/register "
                    "(free 60 req/min). Without it, only GDELT news is used."
                ),
            )
        self._key = settings.finnhub_api_key.get_secret_value()
        self._limiter = RateLimiter(rate=0.9, capacity=5, name="finnhub")  # ~54/min

    def fetch(
        self,
        symbols: list[str],
        *,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsArticle]:
        since = since or datetime.now(UTC) - timedelta(days=2)
        end = datetime.now(UTC)
        articles: list[NewsArticle] = []
        with httpx.Client(timeout=20.0) as client:
            for sym in symbols:
                self._limiter.acquire()
                try:
                    resp = client.get(
                        f"{self.BASE}/company-news",
                        params={
                            "symbol": sym,
                            "from": since.strftime("%Y-%m-%d"),
                            "to": end.strftime("%Y-%m-%d"),
                            "token": self._key,
                        },
                    )
                    if resp.status_code == 429:
                        logger.warning(
                            "finnhub_rate_limited",
                            guidance="Backing off; reduce universe or wait ~60s.",
                        )
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    logger.warning("finnhub_fetch_failed", symbol=sym, error=str(exc))
                    continue
                if not isinstance(data, list):
                    continue
                for item in data[:limit]:
                    ts = item.get("datetime")
                    published = (
                        datetime.fromtimestamp(ts, tz=UTC) if isinstance(ts, (int, float)) else None
                    )
                    headline = str(item.get("headline") or "")
                    if not headline:
                        continue
                    articles.append(
                        NewsArticle(
                            id=f"finnhub:{item.get('id', hash(headline))}",
                            symbol=sym,
                            headline=headline,
                            summary=str(item.get("summary") or ""),
                            source=f"finnhub:{item.get('source', '')}",
                            url=str(item.get("url") or ""),
                            published_at=published,
                            raw=item if isinstance(item, dict) else {},
                        )
                    )
        return articles

    def health_check(self) -> dict[str, Any]:
        try:
            arts = self.fetch(["AAPL"], limit=1)
            return {
                "ok": True,
                "source": self.name,
                "sample": len(arts),
                "guidance": "Finnhub reachable.",
            }
        except Exception as exc:
            return {
                "ok": False,
                "source": self.name,
                "error": str(exc),
                "guidance": "Check FINNHUB_API_KEY and network.",
            }
