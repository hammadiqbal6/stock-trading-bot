"""Local FinBERT sentiment (ProsusAI/finbert). Lazy-loaded."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)

LABEL_MAP = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}


@lru_cache(maxsize=1)
def _load_pipeline() -> Any:
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise RuntimeError(
            "transformers/torch not installed — FinBERT unavailable. "
            "Install deps or set sentiment fallback to neutral."
        ) from exc
    logger.info("loading_finbert", model="ProsusAI/finbert")
    return pipeline("sentiment-analysis", model="ProsusAI/finbert")


class FinBERTScorer:
    name = "finbert"

    def __init__(self, *, lazy: bool = True) -> None:
        self._pipe: Any | None = None
        if not lazy:
            self._pipe = _load_pipeline()

    def score(self, texts: list[str]) -> list[float]:
        if not texts:
            return []
        try:
            pipe = self._pipe or _load_pipeline()
            self._pipe = pipe
        except Exception as exc:
            logger.warning(
                "finbert_unavailable",
                error=str(exc),
                guidance="Returning neutral scores. Check torch/transformers install.",
            )
            return [0.0] * len(texts)

        out: list[float] = []
        for text in texts:
            try:
                result = pipe(text[:512])[0]
                label = str(result.get("label", "neutral")).lower()
                conf = float(result.get("score", 0.0))
                base = LABEL_MAP.get(label, 0.0)
                out.append(base * conf if base != 0 else 0.0)
            except Exception as exc:
                logger.warning("finbert_score_failed", error=str(exc))
                out.append(0.0)
        return out
