"""Anonymise company/ticker names to reduce LLM look-ahead bias (Glasserman & Lin)."""

from __future__ import annotations

import re

from trading_bot.news.gdelt_source import COMPANY_NAMES


def anonymise_text(text: str, symbol: str | None = None) -> str:
    """Replace tickers and known company names with generic tokens."""
    out = text
    replacements: list[tuple[str, str]] = []
    if symbol:
        name = COMPANY_NAMES.get(symbol.upper())
        if name:
            for part in name.split():
                if len(part) > 2:
                    replacements.append((part, "COMPANY"))
        replacements.append((symbol, "TICKER"))
    # Also scrub other known names
    for sym, name in COMPANY_NAMES.items():
        if symbol and sym == symbol.upper():
            continue
        for part in name.split():
            if len(part) > 3:
                replacements.append((part, "ENTITY"))
        replacements.append((sym, "TICKER"))

    # Longer first
    replacements.sort(key=lambda x: len(x[0]), reverse=True)
    for raw, token in replacements:
        out = re.sub(rf"\b{re.escape(raw)}\b", token, out, flags=re.IGNORECASE)
    return out
