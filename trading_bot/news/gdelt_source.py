"""GDELT DOC 2.0 — free, no API key (~1 req / 5s)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

from trading_bot.news.base import NewsArticle, NewsSource
from trading_bot.utils.logging import get_logger
from trading_bot.utils.rate_limit import RateLimiter

logger = get_logger(__name__)

# Company display names for query expansion (keep small / maintainable)
COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Google Alphabet",
    "AMZN": "Amazon",
    "NVDA": "NVIDIA",
    "META": "Meta Facebook",
    "JPM": "JPMorgan",
    "V": "Visa",
    "UNH": "UnitedHealth",
    "XOM": "Exxon",
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
}


class GDELTNewsSource(NewsSource):
    name = "gdelt"
    BASE = "https://api.gdeltproject.org/api/v2/doc/doc"

    def __init__(self) -> None:
        self._limiter = RateLimiter(rate=0.2, capacity=1, name="gdelt")  # ~1/5s

    def fetch(
        self,
        symbols: list[str],
        *,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsArticle]:
        since = since or datetime.now(UTC) - timedelta(hours=48)
        articles: list[NewsArticle] = []
        with httpx.Client(timeout=30.0) as client:
            for sym in symbols:
                query_name = COMPANY_NAMES.get(sym.upper(), sym)
                query = f'("{query_name}" OR {sym}) sourcelang:english'
                self._limiter.acquire()
                try:
                    # GDELT timespan e.g. 48h
                    hours = max(1, int((datetime.now(UTC) - since).total_seconds() // 3600))
                    url = (
                        f"{self.BASE}?query={quote(query)}"
                        f"&mode=ArtList&maxrecords={min(limit, 50)}"
                        f"&timespan={hours}h&format=json&sort=DateDesc"
                    )
                    resp = client.get(url)
                    if resp.status_code != 200:
                        logger.warning(
                            "gdelt_http_error",
                            status=resp.status_code,
                            guidance="GDELT may throttle; wait 5s+ between calls.",
                        )
                        continue
                    payload = resp.json()
                except Exception as exc:
                    logger.warning("gdelt_fetch_failed", symbol=sym, error=str(exc))
                    continue
                docs = payload.get("articles") if isinstance(payload, dict) else None
                if not docs:
                    continue
                for doc in docs:
                    title = str(doc.get("title") or "")
                    if not title:
                        continue
                    seendate = doc.get("seendate")
                    published = None
                    if isinstance(seendate, str) and len(seendate) >= 8:
                        try:
                            published = datetime.strptime(seendate[:15], "%Y%m%dT%H%M%S").replace(
                                tzinfo=UTC
                            )
                        except ValueError:
                            published = None
                    articles.append(
                        NewsArticle(
                            id=f"gdelt:{hash(doc.get('url', title))}",
                            symbol=sym,
                            headline=title,
                            summary="",
                            source=f"gdelt:{doc.get('domain', '')}",
                            url=str(doc.get("url") or ""),
                            published_at=published,
                            raw=doc if isinstance(doc, dict) else {},
                        )
                    )
        return articles

    def health_check(self) -> dict[str, Any]:
        try:
            arts = self.fetch(["AAPL"], limit=3)
            return {
                "ok": True,
                "source": self.name,
                "sample": len(arts),
                "guidance": "GDELT reachable (no API key required).",
            }
        except Exception as exc:
            return {
                "ok": False,
                "source": self.name,
                "error": str(exc),
                "guidance": "GDELT unreachable — check network; no key is required.",
            }
