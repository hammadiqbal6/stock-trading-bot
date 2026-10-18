# Skill: Debug a failing trade

1. Check dashboard **Logs**, **Risk**, and **Setup** panels for guidance strings.
2. Confirm market hours (`MarketCalendar`) and `submit_during_regular_hours_only`.
3. Verify broker health (`/api/health`) — keys, paper vs live, buying power.
4. Inspect risk rejections (position cap, min notional, PDT, kill switch).
5. Partial fills: confirm order status via broker; residual may wait next cycle.
6. Sentiment blocks are intentional — not broker failures.
7. Reproduce with `paper_sim` + `TradingEngine.run_once(submit_orders=False)` if Alpaca outage.
8. Never disable kill switch without `RESET_KILL_SWITCH` and a written reason in logs.
