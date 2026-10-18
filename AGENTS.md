# AGENTS.md — Operating manual for AI agents

This repository is a **paper-first AI stock trading bot**. Read this before changing code.

## Non-negotiables

1. **Paper trading is default.** Live requires `TRADING_MODE=live` + `LIVE_TRADING_ENABLED=true` + `LIVE_TRADING_CONFIRM=I_UNDERSTAND_THE_RISKS` + `ALPACA_PAPER=false`.
2. **LLM / advisory never places orders and never overrides risk** (`AdvisoryConfig` forces these true).
3. **Never claim unproven accuracy.** Surface walk-forward, holdout, fees/slippage, DSR/PBO. Cite research humility (51–55% directional, Sharpe 0.5–1.0 target).
4. **Never commit secrets.** Use `.env.example` only; `.env` is gitignored.
5. **Push small commits** on `cursor/*` branches; keep PR description updated with screenshots/metrics.

## Architecture (layers)

| Layer | Path | Role |
|-------|------|------|
| Config | `trading_bot/config/` | Pydantic settings + YAML |
| Brokers | `trading_bot/brokers/` | Alpaca, paper_sim, IBKR stub |
| Data | `trading_bot/data/` | Alpaca / yfinance + calendar |
| Strategies | `trading_bot/strategies/` | Momentum + optional ML |
| News / Sentiment | `trading_bot/news/`, `sentiment/` | Finnhub, GDELT, FinBERT, LLM |
| Risk | `trading_bot/risk/` | Hard limits / kill switch / PDT |
| Validation | `trading_bot/validation/` | Walk-forward, DSR, PBO proxy |
| Advisory | `trading_bot/advisory/` | Research-only multi-agent |
| Services | `trading_bot/services/` | `TradingEngine` orchestration |
| API / UI | `trading_bot/api/` | FastAPI + Meridian dashboard |

## Commands

```bash
make install-dev
make lint
make test
make test-e2e
make sample-validation
make api
```

## Do

- Add brokers/strategies/news/LLM via interfaces (`Broker`, `Strategy`, `NewsSource`, `LLMSentimentProvider`).
- Return **actionable `guidance`** on every failure path (UI + logs).
- Keep types; run ruff; add pytest for new logic.
- Update `docs/` + README account table when adding integrations.
- Prefer weekly/monthly rebalance (PDT-friendly).

## Don't

- Don't let LLM output call `submit_order`.
- Don't use yfinance as the sole live execution data path in production configs.
- Don't weaken kill switch / daily loss / max DD checks.
- Don't add Vision-LLM chart readers or claim TradingAgents-like Sharpe 8.x.
- Don't store API keys in repo, tests, or screenshots.

## Subagents / auditors

See `.cursor/agents/` — code auditor, risk/safety auditor, backtest-validity auditor, UI QA, docs maintainer.

## Skills

See `.cursor/skills/*/SKILL.md` for recurring tasks (add strategy, add data source, run validation, add LLM provider, deploy, debug trade).
