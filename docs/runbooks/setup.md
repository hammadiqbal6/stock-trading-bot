# Runbook: Setup

1. `cp .env.example .env`
2. Create Alpaca **paper** account → set `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`.
3. Optional: Finnhub + Groq keys.
4. `pip install -e ".[dev]"` then `make api`.
5. Open http://127.0.0.1:8000 → **Setup** wizard should show green Alpaca.
6. Without Alpaca keys, engine uses `paper_sim` (demo only).

Pakistan: Alpaca paper is available worldwide; GDELT/FinBERT/yfinance need no signup.
