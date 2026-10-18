"""Sentiment pipeline: cache → LLM (optional) → FinBERT fallback → neutral."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from pydantic import BaseModel, Field

from trading_bot.config.settings import Settings, get_settings
from trading_bot.news.base import NewsArticle
from trading_bot.sentiment.anonymize import anonymise_text
from trading_bot.sentiment.finbert import FinBERTScorer
from trading_bot.sentiment.llm import get_llm_provider
from trading_bot.utils.exceptions import LLMProviderError
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


class SentimentResult(BaseModel):
    symbol: str
    score: float
    n_articles: int = 0
    method: str = "neutral"
    headlines: list[str] = Field(default_factory=list)
    guidance: str = ""


class SentimentPipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.finbert = FinBERTScorer(lazy=True)
        self.llm = None
        try:
            self.llm = get_llm_provider(self.settings)
        except LLMProviderError as exc:
            logger.warning("llm_init_failed", error=str(exc), guidance=exc.guidance)
        self.cache_path = self.settings.cache_dir / "sentiment_cache.json"
        self._cache = self._load_cache()

    def score_articles(self, articles: list[NewsArticle]) -> dict[str, SentimentResult]:
        by_symbol: dict[str, list[NewsArticle]] = {}
        for a in articles:
            sym = (a.symbol or "MARKET").upper()
            by_symbol.setdefault(sym, []).append(a)

        results: dict[str, SentimentResult] = {}
        for sym, arts in by_symbol.items():
            results[sym] = self._score_symbol(sym, arts)
        return results

    def _score_symbol(self, symbol: str, arts: list[NewsArticle]) -> SentimentResult:
        if not arts:
            return SentimentResult(
                symbol=symbol,
                score=0.0,
                method="neutral",
                guidance="No recent articles — neutral sentiment assumed.",
            )

        headlines = [a.headline for a in arts[:10]]
        cache_key = hashlib.sha256(f"{symbol}|{'||'.join(headlines)}".encode()).hexdigest()
        cached = self._cache.get(cache_key)
        ttl = self.settings.yaml.sentiment.cache_ttl_hours * 3600
        if cached and time.time() - cached.get("ts", 0) < ttl:
            return SentimentResult.model_validate(cached["result"])

        texts = []
        for h in headlines:
            if self.settings.yaml.sentiment.anonymise_entities:
                texts.append(anonymise_text(h, symbol))
            else:
                texts.append(h)

        method = "finbert"
        scores: list[float] = []
        guidance = ""

        if self.llm is not None:
            try:
                scores = self.llm.score_texts(texts)
                method = self.llm.name
            except Exception as exc:
                logger.warning(
                    "llm_sentiment_failed_fallback",
                    error=str(exc),
                    guidance="Falling back to FinBERT/neutral.",
                )
                guidance = f"LLM failed ({exc}); used FinBERT/neutral fallback."

        if not scores:
            if self.settings.yaml.sentiment.fallback == "finbert":
                scores = self.finbert.score(texts)
                method = "finbert"
            else:
                scores = [0.0] * len(texts)
                method = "neutral"
                guidance = guidance or "Neutral fallback configured."

        avg = float(sum(scores) / len(scores)) if scores else 0.0
        result = SentimentResult(
            symbol=symbol,
            score=avg,
            n_articles=len(arts),
            method=method,
            headlines=headlines[:5],
            guidance=guidance
            or (
                f"Sentiment via {method}. Strongly negative may block entries; "
                "LLM never overrides hard risk rules."
            ),
        )
        self._cache[cache_key] = {"ts": time.time(), "result": result.model_dump(mode="json")}
        self._save_cache()
        return result

    def health_check(self) -> dict[str, Any]:
        out: dict[str, Any] = {"finbert": "lazy", "llm": None}
        if self.llm:
            out["llm"] = self.llm.health_check()
        else:
            out["llm"] = {
                "ok": True,
                "provider": "none",
                "guidance": "LLM disabled — FinBERT/neutral only.",
            }
        return out

    def _load_cache(self) -> dict[str, Any]:
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_cache(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            # keep cache bounded
            if len(self._cache) > 2000:
                items = sorted(self._cache.items(), key=lambda x: x[1].get("ts", 0), reverse=True)
                self._cache = dict(items[:1000])
            self.cache_path.write_text(json.dumps(self._cache), encoding="utf-8")
        except Exception as exc:
            logger.warning("sentiment_cache_write_failed", error=str(exc))
