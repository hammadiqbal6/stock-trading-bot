# Strategy: volatility-scaled momentum

## Idea
Time-series trend is the strongest evidence-backed sleeve (Hurst, Ooi & Pedersen). We long names with positive trailing return, scale by inverse volatility toward an annual vol target, and tilt with cross-sectional momentum among large caps.

## Filters
- Strongly negative 1–2 day news sentiment can **block new entries**.
- Mildly positive sentiment can slightly size up (configurable).
- Optional ML score nudges weights ±10% relative — walk-forward only.

## Rebalance
Weekly (default) or monthly — reduces PDT pressure vs day trading.

## What it is not
Not an LLM day-trader. Not a guarantee of alpha after costs.
