# Architecture overview

Meridian is a layered Python service:

1. **Config** — `Settings` (env) merges `config/settings.yaml`.
2. **TradingEngine** — one cycle: data → sentiment → strategy → risk → broker orders; advisory is side-channel only.
3. **Brokers** — `Broker` ABC; Alpaca paper default; `paper_sim` without keys; IBKR stub.
4. **Data** — Alpaca for live path; yfinance for backtests/validation.
5. **Risk** — hard gate before every order batch.
6. **API/UI** — FastAPI JSON + Meridian HTML desk.

See root `README.md` mermaid diagram and `AGENTS.md`.
