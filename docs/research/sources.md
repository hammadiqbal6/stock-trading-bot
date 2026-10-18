# Research sources

Compiled for Sidney (Pakistan-based), Oct 18 2026. Full narrative: [`verified_research.md`](verified_research.md).

## Accuracy & LLM trading
- Lopez-Lira & Tang — ChatGPT / news return predictability (arXiv 2304.07619; JFE 2026)
- Kirtac & Germano — OPT vs FinBERT sentiment (arXiv 2412.19245)
- Glasserman & Lin — anonymise entity names to reduce look-ahead bias
- FINSABER — LLM agents vs buy-and-hold 2004–2024 (arXiv 2505.07078, KDD 2026; https://github.com/waylonli/FINSABER)
- Alpha Arena S1 — frontier LLMs on real-money crypto perps (large drawdowns / overtrading)

## Classic quant evidence
- Hurst, Ooi & Pedersen (2017) — time-series momentum across markets
- Moreira & Muir (2017) — volatility-managed portfolios
- McLean & Pontiff — post-publication decay of anomalies
- Bailey & López de Prado — deflated Sharpe / PBO
- Gu, Kelly & Xiu (RFS 2020) — ML on characteristics (tiny R², portfolio-level edge)
- Bajgrowicz & Scaillet (JFE 2012) — technical rules & data-snooping

## Stack references
- Alpaca paper trading docs — https://docs.alpaca.markets (paper-api.alpaca.markets)
- alpaca-py — Python SDK
- FinBERT — ProsusAI/finbert (Hugging Face)
- TradingAgents — https://github.com/TauricResearch/TradingAgents (Apache-2.0; advisory inspiration only)
- GDELT DOC 2.0 API — no key
- Finnhub company news — free tier 60/min
- Groq free tier — Llama 3.1 rate limits
- vectorbt — walk-forward / portfolio research
- TA libraries — `ta`, pandas-ta-classic, TA-Lib

## Design implication
Prefer volatility-scaled trend + cross-sectional tilt + soft news filter; validate with walk-forward, holdout after LLM cutoff, costs, DSR/PBO; never let LLM place orders or override risk.
