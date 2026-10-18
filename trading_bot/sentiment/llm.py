"""Pluggable LLM sentiment providers (Groq default free tier, Ollama, OpenAI-compatible)."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from trading_bot.config.settings import LLMProvider, Settings
from trading_bot.utils.exceptions import LLMProviderError
from trading_bot.utils.logging import get_logger
from trading_bot.utils.rate_limit import RateLimiter

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a financial news sentiment classifier. "
    "Given anonymised headlines about COMPANY/TICKER/ENTITY, "
    'respond with JSON only: {"score": <float from -1 to 1>, "label": '
    '"negative"|"neutral"|"positive"}. '
    "Do not invent facts. If unclear, score 0."
)


class LLMSentimentProvider(ABC):
    name: str

    @abstractmethod
    def score_texts(self, texts: list[str]) -> list[float]: ...

    @abstractmethod
    def health_check(self) -> dict[str, Any]: ...


def _parse_score(content: str) -> float:
    content = content.strip()
    try:
        # Extract JSON object
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            score = float(data.get("score", 0.0))
            return max(-1.0, min(1.0, score))
    except Exception:
        pass
    lower = content.lower()
    if "positive" in lower:
        return 0.5
    if "negative" in lower:
        return -0.5
    return 0.0


class GroqSentimentProvider(LLMSentimentProvider):
    name = "groq"

    def __init__(self, settings: Settings) -> None:
        if not settings.has_groq():
            raise LLMProviderError(
                "groq",
                "GROQ_API_KEY missing — get a free key at https://console.groq.com/keys",
            )
        from groq import Groq

        self._client = Groq(api_key=settings.groq_api_key.get_secret_value())
        self._model = settings.groq_model
        # Free tier ~30 rpm
        self._limiter = RateLimiter(rate=0.4, capacity=5, name="groq")

    def score_texts(self, texts: list[str]) -> list[float]:
        scores: list[float] = []
        for text in texts:
            self._limiter.acquire()
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text[:1500]},
                    ],
                    temperature=0,
                    max_tokens=64,
                )
                content = resp.choices[0].message.content or "0"
                scores.append(_parse_score(content))
            except Exception as exc:
                logger.warning("groq_failed", error=str(exc))
                raise LLMProviderError("groq", str(exc)) from exc
        return scores

    def health_check(self) -> dict[str, Any]:
        try:
            s = self.score_texts(["COMPANY reported unchanged quarterly results."])
            return {"ok": True, "provider": self.name, "sample_score": s[0]}
        except Exception as exc:
            return {
                "ok": False,
                "provider": self.name,
                "error": str(exc),
                "guidance": "Check GROQ_API_KEY and free-tier rate limits (30 rpm).",
            }


class OllamaSentimentProvider(LLMSentimentProvider):
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.base = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self._limiter = RateLimiter(rate=1.0, capacity=2, name="ollama")

    def score_texts(self, texts: list[str]) -> list[float]:
        scores: list[float] = []
        with httpx.Client(timeout=60.0) as client:
            for text in texts:
                self._limiter.acquire()
                try:
                    resp = client.post(
                        f"{self.base}/api/chat",
                        json={
                            "model": self.model,
                            "stream": False,
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": text[:1500]},
                            ],
                        },
                    )
                    resp.raise_for_status()
                    content = resp.json().get("message", {}).get("content", "0")
                    scores.append(_parse_score(content))
                except Exception as exc:
                    raise LLMProviderError("ollama", str(exc)) from exc
        return scores

    def health_check(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(f"{self.base}/api/tags")
                return {
                    "ok": r.status_code == 200,
                    "provider": self.name,
                    "guidance": "Ollama reachable." if r.status_code == 200 else "Ollama down.",
                }
        except Exception as exc:
            return {
                "ok": False,
                "provider": self.name,
                "error": str(exc),
                "guidance": f"Start Ollama locally ({self.base}) or switch LLM_PROVIDER=none.",
            }


class OpenAICompatibleProvider(LLMSentimentProvider):
    name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        key = settings.openai_api_key.get_secret_value().strip()
        if not key:
            raise LLMProviderError("openai_compatible", "OPENAI_API_KEY missing")
        self.base = settings.openai_base_url.rstrip("/")
        self.model = settings.openai_model
        self.key = key
        self._limiter = RateLimiter(rate=0.5, capacity=3, name="openai")

    def score_texts(self, texts: list[str]) -> list[float]:
        scores: list[float] = []
        with httpx.Client(timeout=45.0) as client:
            for text in texts:
                self._limiter.acquire()
                try:
                    resp = client.post(
                        f"{self.base}/chat/completions",
                        headers={"Authorization": f"Bearer {self.key}"},
                        json={
                            "model": self.model,
                            "temperature": 0,
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": text[:1500]},
                            ],
                        },
                    )
                    resp.raise_for_status()
                    content = (
                        resp.json()["choices"][0]["message"]["content"]
                        if resp.json().get("choices")
                        else "0"
                    )
                    scores.append(_parse_score(content))
                except Exception as exc:
                    raise LLMProviderError("openai_compatible", str(exc)) from exc
        return scores

    def health_check(self) -> dict[str, Any]:
        return {"ok": bool(self.key), "provider": self.name, "guidance": "Key configured."}


def get_llm_provider(settings: Settings) -> LLMSentimentProvider | None:
    if settings.llm_provider == LLMProvider.NONE:
        return None
    if settings.llm_provider == LLMProvider.GROQ:
        return GroqSentimentProvider(settings)
    if settings.llm_provider == LLMProvider.OLLAMA:
        return OllamaSentimentProvider(settings)
    if settings.llm_provider == LLMProvider.OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(settings)
    return None
