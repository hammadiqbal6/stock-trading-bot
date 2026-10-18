# ADR 0003: LLM is advisory / sentiment only

## Status
Accepted

## Context
Research shows LLM trading agents often fail long-horizon vs buy-and-hold (FINSABER); Alpha Arena showed large live losses from overtrading.

## Decision
LLMs may score sentiment and produce advisory research notes. They never place orders or override risk. Entity names are anonymised (Glasserman & Lin).

## Consequences
- Safer default behavior.
- Sentiment is a soft tilt/filter only.
