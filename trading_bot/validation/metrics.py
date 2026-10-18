"""Honest performance metrics including deflated Sharpe and PBO approximation."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


def performance_metrics(
    returns: pd.Series,
    *,
    risk_free_rate: float = 0.04,
    periods_per_year: int = 252,
) -> dict[str, float]:
    r = returns.dropna().astype(float)
    if r.empty:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "vol_annual": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "hit_rate": 0.0,
            "n_obs": 0.0,
        }
    total = float((1 + r).prod() - 1)
    n = len(r)
    years = n / periods_per_year
    cagr = float((1 + total) ** (1 / years) - 1) if years > 0 and (1 + total) > 0 else 0.0
    vol = float(r.std(ddof=1) * math.sqrt(periods_per_year)) if n > 1 else 0.0
    excess = r - risk_free_rate / periods_per_year
    sharpe = (
        float(excess.mean() / excess.std(ddof=1) * math.sqrt(periods_per_year))
        if excess.std(ddof=1) > 0
        else 0.0
    )
    equity = (1 + r).cumprod()
    drawdown = equity / equity.cummax() - 1
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    hit = float((r > 0).mean())
    return {
        "total_return": total,
        "cagr": cagr,
        "vol_annual": vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "hit_rate": hit,
        "n_obs": float(n),
    }


def deflated_sharpe_ratio(
    sharpe: float,
    *,
    n_obs: int,
    n_trials: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    sharpe_benchmark: float = 0.0,
) -> dict[str, float]:
    """Bailey & López de Prado deflated Sharpe ratio (approx).

    Returns DSR and probability that observed SR is significant given multiple trials.
    """
    if n_obs <= 1 or n_trials < 1:
        return {"dsr": 0.0, "psr": 0.0, "sr_star": 0.0}

    # Expected max SR under null across n_trials (Euler-Mascheroni approx)
    euler = 0.5772156649
    sr_star = sharpe_benchmark + math.sqrt(1 / (n_obs - 1)) * (
        (1 - euler) * stats.norm.ppf(1 - 1 / n_trials)
        + euler * stats.norm.ppf(1 - 1 / (n_trials * math.e))
    )

    # Probabilistic Sharpe Ratio vs sr_star
    sr = sharpe
    denom = math.sqrt(
        max(
            1e-12,
            (1 - skew * sr + (kurtosis - 1) / 4 * sr**2) / (n_obs - 1),
        )
    )
    psr = float(stats.norm.cdf((sr - sr_star) / denom))
    dsr = psr  # commonly reported as the deflated SR probability
    return {"dsr": dsr, "psr": psr, "sr_star": float(sr_star)}


def probabilistic_backtest_overfitting(
    fold_sharpes: list[float],
    *,
    n_strategies: int = 1,
) -> dict[str, Any]:
    """Simplified PBO-style indicator.

    Full CSCV PBO (Bailey et al.) needs many strategy variants. Here we report:
    - fraction of walk-forward folds with Sharpe <= 0
    - a conservative PBO proxy using fold relative ranks when n_strategies>1

    Honest interpretation: high fail_fraction / high pbo_proxy ⇒ distrust the edge.
    """
    arr = np.array([s for s in fold_sharpes if s is not None], dtype=float)
    if arr.size == 0:
        return {"pbo_proxy": 1.0, "fail_fraction": 1.0, "n_folds": 0, "note": "no folds"}
    fail_fraction = float((arr <= 0).mean())
    # Conservative proxy: if multiple strategies not provided, use fail_fraction
    pbo_proxy = fail_fraction
    if n_strategies > 1:
        # Without full CSCV matrix, inflate fail fraction toward 1 as trials grow
        pbo_proxy = float(min(1.0, fail_fraction + 0.05 * math.log(n_strategies)))
    return {
        "pbo_proxy": pbo_proxy,
        "fail_fraction": fail_fraction,
        "n_folds": int(arr.size),
        "mean_fold_sharpe": float(arr.mean()),
        "note": (
            "Simplified PBO proxy (not full CSCV). Treat as an overfitting warning light, "
            "not a precise Bailey PBO estimate."
        ),
    }


def apply_costs(returns: pd.Series, turnover: pd.Series, *, fee_bps: float, slippage_bps: float) -> pd.Series:
    cost = turnover.abs() * (fee_bps + slippage_bps) / 10_000.0
    return returns - cost.reindex(returns.index).fillna(0.0)
