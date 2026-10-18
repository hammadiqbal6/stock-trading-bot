# Skill: Run backtest / walk-forward validation

1. Prefer `make sample-validation` or `python -m trading_bot.cli validate`.
2. Use yfinance for history; never claim live Alpaca SIP without credentials.
3. Confirm report includes: fold Sharpes, holdout vs buy-and-hold, fees/slippage, DSR, PBO proxy, honest disclaimer.
4. Holdout start should be after typical LLM cutoffs (`validation.holdout_start`).
5. If Sharpe looks “too good”, assume bug/lookahead — run backtest-validity auditor.
6. Save JSON under `data/cache/validation_report.json` for the dashboard.
7. Do not tune parameters against the holdout.
