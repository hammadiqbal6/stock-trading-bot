# Sample validation results (2019 → 2026-10-18)

Universe: SPY, QQQ, IWM, TLT, GLD, EFA, XLE, AAPL, MSFT, JPM  
Costs: fee 5.0 bps + slippage 5.0 bps · weekly rebalance  
Holdout start: `2024-07-01`

| Slice | Sharpe | Max DD | Hit rate | Notes |
|-------|--------|--------|----------|-------|
| Walk-forward OOS (combined) | 0.70 | -24.2% | 55.4% | 884 days |
| Holdout (strategy) | 0.71 | -11.6% | 54.9% | after LLM cutoff |
| Holdout buy & hold | 1.05 | -15.7% | 55.9% | equal-weight universe |
| DSR / PSR | 1.00 | — | — | vs multi-trial null |
| PBO proxy | 0.40 | — | — | Simplified PBO proxy (not full CSCV). Treat as an overfitting warning light, not a precise Bailey PBO estimate. |

**Guidance:** Walk-forward folds=4, holdout from 2024-07-01. OOS Sharpe=0.70, DSR/PSR=1.00, PBO proxy=0.40. Holdout Sharpe 0.71 vs buy&hold 1.05 (buy&hold ahead / inconclusive). Costs applied (fees+slippage). Do not deploy live without paper-trade concordance.

**Honesty:** No free method reliably beats ~51-55% daily directional accuracy OOS. Target Sharpe 0.5–1.0 after costs. Halve published edges. LLM agents often fail to beat buy-and-hold on long horizons (FINSABER).

Raw JSON: [`sample_report.json`](sample_report.json)
