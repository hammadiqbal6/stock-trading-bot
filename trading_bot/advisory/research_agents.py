"""Multi-agent LLM analysis as an advisory research layer.

HARD RULES (enforced):
- never places orders
- never overrides risk engine decisions
- output is informational for the dashboard / logs only
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from trading_bot.config.settings import Settings, get_settings
from trading_bot.sentiment.anonymize import anonymise_text
from trading_bot.sentiment.llm import SYSTEM_PROMPT, get_llm_provider
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


class AdvisoryReport(BaseModel):
    symbol: str
    fundamental: str = ""
    sentiment: str = ""
    technical: str = ""
    risk: str = ""
    consensus: str = "hold"
    confidence: float = 0.0
    advisory_only: bool = True
    places_orders: bool = False
    overrides_risk: bool = False
    guidance: str = (
        "Advisory research only. Does not place trades or override risk limits. "
        "Published multi-agent LLM Sharpes (e.g. TradingAgents 8.2) are not credible "
        "for live allocation; FINSABER finds LLM agents often lag buy-and-hold."
    )
    raw: dict[str, Any] = Field(default_factory=dict)


class AdvisoryResearchLayer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        assert self.settings.yaml.advisory.never_place_orders is True
        assert self.settings.yaml.advisory.never_override_risk is True
        self.llm = None
        try:
            self.llm = get_llm_provider(self.settings)
        except Exception as exc:  # noqa: BLE001
            logger.info("advisory_llm_unavailable", error=str(exc))

    @property
    def enabled(self) -> bool:
        return bool(self.settings.yaml.advisory.enabled)

    def analyze(
        self,
        symbol: str,
        *,
        headlines: list[str] | None = None,
        technical_summary: str = "",
        risk_summary: str = "",
    ) -> AdvisoryReport:
        if not self.enabled:
            return AdvisoryReport(
                symbol=symbol,
                consensus="disabled",
                guidance="Advisory layer disabled (ENABLE_TRADING_AGENTS_ADVISORY=false).",
            )

        headlines = headlines or []
        anon = [anonymise_text(h, symbol) for h in headlines[:5]]
        # Heuristic local consensus when LLM unavailable
        if self.llm is None:
            return AdvisoryReport(
                symbol=symbol,
                fundamental="LLM unavailable — skipped fundamental agent.",
                sentiment=f"{len(anon)} headlines on file; no LLM scoring.",
                technical=technical_summary or "See strategy signals panel.",
                risk=risk_summary or "Hard risk engine remains authoritative.",
                consensus="hold",
                confidence=0.0,
                guidance=(
                    "Advisory ran in degraded mode (no LLM). "
                    "Enable GROQ/Ollama for multi-agent notes. Still never places orders."
                ),
            )

        prompt = (
            "You are coordinating four research agents (fundamental, sentiment, technical, risk) "
            "for an anonymised equity. Return JSON: "
            '{"fundamental":str,"sentiment":str,"technical":str,"risk":str,'
            '"consensus":"buy"|"hold"|"sell","confidence":0..1}. '
            "Be conservative. This is research only.\n\n"
            f"Headlines: {json.dumps(anon)}\n"
            f"Technical: {technical_summary}\n"
            f"Risk: {risk_summary}\n"
        )
        try:
            # Reuse provider scoring channel via a single chat-like call when possible
            from trading_bot.sentiment.llm import GroqSentimentProvider, OllamaSentimentProvider

            text = prompt
            # Providers expose score_texts; for advisory we ask for JSON via same chat APIs
            if isinstance(self.llm, GroqSentimentProvider):
                self.llm._limiter.acquire()  # noqa: SLF001
                resp = self.llm._client.chat.completions.create(  # noqa: SLF001
                    model=self.llm._model,  # noqa: SLF001
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text[:4000]},
                    ],
                    temperature=0.2,
                    max_tokens=400,
                )
                content = resp.choices[0].message.content or "{}"
            elif isinstance(self.llm, OllamaSentimentProvider):
                import httpx

                self.llm._limiter.acquire()  # noqa: SLF001
                with httpx.Client(timeout=90.0) as client:
                    r = client.post(
                        f"{self.llm.base}/api/chat",
                        json={
                            "model": self.llm.model,
                            "stream": False,
                            "messages": [
                                {"role": "system", "content": "Return JSON only."},
                                {"role": "user", "content": text[:4000]},
                            ],
                        },
                    )
                    r.raise_for_status()
                    content = r.json().get("message", {}).get("content", "{}")
            else:
                content = "{}"
            data = _extract_json(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("advisory_failed", error=str(exc))
            return AdvisoryReport(
                symbol=symbol,
                consensus="hold",
                guidance=f"Advisory LLM failed ({exc}); ignoring. Risk engine unchanged.",
            )

        return AdvisoryReport(
            symbol=symbol,
            fundamental=str(data.get("fundamental", "")),
            sentiment=str(data.get("sentiment", "")),
            technical=str(data.get("technical", technical_summary)),
            risk=str(data.get("risk", risk_summary)),
            consensus=str(data.get("consensus", "hold")),
            confidence=float(data.get("confidence", 0) or 0),
            raw=data,
        )


def _extract_json(content: str) -> dict[str, Any]:
    import re

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group())
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
