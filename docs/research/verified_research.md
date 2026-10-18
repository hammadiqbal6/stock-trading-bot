# AI Trading Bot Research (Oct 18, 2026, compiled for Sidney, Pakistan-based)

## Realistic accuracy
- No free method/indicator/AI model reliably beats ~51-55% daily directional accuracy out-of-sample.
- LLM news sentiment: Lopez-Lira & Tang (arXiv 2304.07619, JFE 2026): ~58% on tradable 1-2 day drift for overnight news, ~34bps/day pre-cost, fading as LLM adoption grows. Kirtac & Germano (arXiv 2412.19245): OPT 74.4% / FinBERT 72.2% direction accuracy, partly in-sample. Glasserman & Lin: anonymise entity names to reduce look-ahead bias. FINSABER (arXiv 2505.07078, KDD 2026, https://github.com/waylonli/FINSABER): LLM agents FinMem/FinAgent do NOT beat buy-and-hold over 2004-2024. Alpha Arena S1 (real money, crypto perps, 2 weeks): most frontier LLMs lost 40-60%, overtrading/fees.
- Target Sharpe 0.5-1.0 after costs. Halve any published edge (McLean & Pontiff: -26% OOS, -58% post-publication).

## Strategies with evidence
- Time-series momentum / trend-following (strongest): Hurst, Ooi & Pedersen 2017, 67 markets 1880-2016, 11.0%/yr after costs, Sharpe 0.76. Crypto: Liu & Tsyvinski RFS 2021, weekly BTC momentum predicts 1-4 weeks.
- Cross-sectional momentum: crypto large caps (Liu, Tsyvinski & Wu JF 2022), 1-4 week; not small coins.
- Crypto carry (basis/funding): BIS WP 1087, BTC/ETH basis ~7%/yr 2019-2024; liquidation/exchange risk; needs derivatives (Bybit).
- Volatility targeting/regime filters: use for risk control (Moreira & Muir 2017; Cederburg 2020 shows no robust OOS return gain).
- Single technical rules fail after data-snooping + costs (Bajgrowicz & Scaillet JFE 2012, 7,846 rules). Chart patterns informative but not proven profitable (Lo, Mamaysky & Wang 2000).
- Mean reversion: unverified for retail after costs.

## Reading charts
- Indicators (TA-Lib https://github.com/TA-Lib/ta-lib-python, pandas-ta-classic https://github.com/xgboosted/pandas-ta-classic, ta https://github.com/bukosabino/ta) as ML features, not standalone signals. Original pandas-ta was removed from GitHub.
- LSTM (Fischer & Krauss 2018): edge ~0 after costs post-2010.
- ML on features (Gu, Kelly & Xiu RFS 2020): tiny R2 but profitable at portfolio level; gradient boosting retrained walk-forward.
- CNN on chart images (Jiang, Kelly & Xiu JF 2023): mostly small-cap, high turnover.
- Zero-shot Chronos/TimesFM: ~51% or below on returns. Kronos (https://github.com/shiyu-coder/Kronos, MIT): modest RankIC ~0.025, test as feature only.
- Vision-LLMs reading chart screenshots: ~49-51%, coin flip. Do not use.

## Free stack
### Crypto
- Exchange: Bybit Demo Trading (https://bybit-exchange.github.io/docs/v5/demo, api-demo.bybit.com, pybit demo=True); open to Pakistan. Backup: Binance Spot Testnet (https://testnet.binance.vision); Binance not licensed in Pakistan.
- Data: CCXT, Bybit funding/basis, CoinGecko Demo (100/min, 10k/month).
- News: GDELT DOC 2.0 (free, no key, ~1 req/5s), crypto RSS (CoinDesk, Cointelegraph etc), Reddit API (free non-commercial, 100 qpm; new access reportedly closes Oct 31 2026, unverified). CryptoPanic no longer free. pytrends archived.
- Sentiment: FinBERT (ProsusAI/finbert, local CPU) then Groq free tier (Llama 3.1 8B: 30 rpm / 14,400/day) with entity names stripped. Optional Ollama local.
- Base: freqtrade (https://github.com/freqtrade/freqtrade, GPL-3.0) with FreqAI sliding-window retraining, lookahead-analysis and recursive-analysis; hold out a later period; vectorbt for walk-forward sweeps.
### Stocks
- Broker: Alpaca paper-only account (anyone globally, email only, https://docs.alpaca.markets/us/docs/paper-trading, paper-api.alpaca.markets, IEX data). Real money later: IBKR (accepts Pakistan). OANDA does not accept Pakistan.
- Data: Alpaca Market Data Basic (200 calls/min, IEX realtime, SIP 15-min delayed); yfinance for backtests only.
- News: Finnhub free (60/min, company news), GDELT. NewsAPI free tier is dev-only (not production).
- Sentiment: FinBERT + Groq/Ollama, anonymised headlines.
- Reference: TradingAgents (https://github.com/TauricResearch/TradingAgents, Apache-2.0) multi-agent LLM analysis; its published Sharpe 8.2 on 3 stocks/5 months is not credible. alpaca-py for orders. vectorbt for walk-forward validation; FINSABER-style long-horizon checks.

## Recommended combined design
1. Core: volatility-scaled time-series trend across diversified universe (crypto: BTC, ETH, large caps; stocks: ETFs + large caps, monthly/weekly rebalance).
2. Tilt: cross-sectional momentum among large caps.
3. Filter: news sentiment over 1-2 days (block entries on strongly negative, small size-up on positive). LLM never decides trades alone and never overrides risk rules.
4. Optional ML: gradient boosting on indicator features retrained walk-forward.
5. Crypto optional: delta-neutral funding/basis carry with margin buffers.
6. Risk: position limits, stop-loss, daily loss cap, max drawdown kill switch, volatility targeting.
7. Validation gate: walk-forward, purged CV, deflated Sharpe > 0, low probability of backtest overfitting (Bailey et al.), holdout after the LLM cutoff with fees/slippage, then 4-8 weeks paper trading matching backtest.
