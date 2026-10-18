# Validation methodology

1. **Walk-forward** expanding windows on pre-holdout data with purge/embargo days.
2. **Holdout** from `validation.holdout_start` (default 2024-07-01) — untouched after typical LLM cutoffs; no tuning.
3. **Costs:** fee_bps + slippage_bps applied via turnover.
4. **Metrics:** total return, CAGR, vol, Sharpe, max drawdown, hit rate.
5. **Deflated Sharpe (DSR/PSR)** after Bailey & López de Prado (approx).
6. **PBO proxy:** fold fail-fraction based warning (not full CSCV); treat as caution light.
7. **Benchmark:** equal-weight buy-and-hold on the same universe (FINSABER-style humility).

**Honesty rule:** never advertise &gt;55% daily directional accuracy; target Sharpe 0.5–1.0 after costs; halve published edges.
