# Runbook: Troubleshooting

| Symptom | Guidance |
|---------|----------|
| Missing Alpaca keys | Setup wizard + `.env`; or accept `paper_sim` |
| Market closed errors | Expected outside NYSE hours; wait for next open |
| 429 / rate limits | Finnhub 60/min, GDELT ~1/5s, Groq ~30 rpm — backoff built-in |
| Empty yfinance data | Network/Yahoo outage; retry or use fixtures |
| Kill switch on | Review daily loss/DD; reset only with `RESET_KILL_SWITCH` |
| LLM failures | Falls back to FinBERT/neutral automatically |
| Insufficient buying power | Reduce weights or top up paper funds |
| PDT warning | Prefer weekly rebalance; equity &lt; $25k → max 3 day trades / 5 days |
| IBKR selected | Stub only — switch `execution.broker` to `alpaca` or `paper_sim` |
