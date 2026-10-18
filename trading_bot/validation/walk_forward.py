"""Walk-forward + holdout validation for the momentum strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from trading_bot.config.settings import Settings, get_settings
from trading_bot.strategies.momentum import VolatilityScaledMomentumStrategy
from trading_bot.utils.logging import get_logger
from trading_bot.validation.metrics import (
    apply_costs,
    deflated_sharpe_ratio,
    performance_metrics,
    probabilistic_backtest_overfitting,
)

logger = get_logger(__name__)


@dataclass
class WalkForwardResult:
    fold_metrics: list[dict[str, float]] = field(default_factory=list)
    oos_returns: pd.Series | None = None
    holdout_metrics: dict[str, float] = field(default_factory=dict)
    buy_hold_metrics: dict[str, float] = field(default_factory=dict)
    combined_metrics: dict[str, float] = field(default_factory=dict)
    dsr: dict[str, float] = field(default_factory=dict)
    pbo: dict[str, Any] = field(default_factory=dict)
    guidance: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fold_metrics": self.fold_metrics,
            "holdout_metrics": self.holdout_metrics,
            "buy_hold_metrics": self.buy_hold_metrics,
            "combined_metrics": self.combined_metrics,
            "dsr": self.dsr,
            "pbo": self.pbo,
            "guidance": self.guidance,
            "meta": self.meta,
            "honest_disclaimer": (
                "No free method reliably beats ~51-55% daily directional accuracy OOS. "
                "Target Sharpe 0.5–1.0 after costs. Halve published edges. "
                "LLM agents often fail to beat buy-and-hold on long horizons (FINSABER)."
            ),
        }


def _simulate_portfolio(
    close: pd.DataFrame,
    *,
    strategy: VolatilityScaledMomentumStrategy,
    rebalance_every: int,
    fee_bps: float,
    slippage_bps: float,
) -> tuple[pd.Series, pd.Series]:
    """Simple next-open/close proxy: weights decided on day t, earn return t→t+1."""
    dates = close.index
    weights = pd.DataFrame(0.0, index=dates, columns=close.columns)
    for i in range(strategy.config.min_history_days, len(dates)):
        if (i - strategy.config.min_history_days) % rebalance_every != 0:
            weights.iloc[i] = weights.iloc[i - 1]
            continue
        window = close.iloc[: i + 1]
        targets = strategy.generate_targets(window)
        w = {t.symbol: t.weight for t in targets if t.weight > 0}
        row = {sym: float(w.get(sym, 0.0)) for sym in close.columns}
        weights.iloc[i] = pd.Series(row, index=close.columns)
        # cash residual implicit

    asset_rets = close.pct_change().fillna(0.0)
    # Use previous day weights
    lagged = weights.shift(1).fillna(0.0)
    port_rets = (lagged * asset_rets).sum(axis=1)
    turnover = lagged.diff().abs().sum(axis=1).fillna(0.0)
    net = apply_costs(port_rets, turnover, fee_bps=fee_bps, slippage_bps=slippage_bps)
    return net, turnover


def run_walk_forward(
    close: pd.DataFrame,
    settings: Settings | None = None,
    *,
    n_trials_for_dsr: int = 20,
) -> WalkForwardResult:
    settings = settings or get_settings()
    cfg = settings.yaml.validation
    strategy = VolatilityScaledMomentumStrategy(settings.yaml.strategy)
    rebalance_every = 5 if settings.yaml.strategy.rebalance == "weekly" else 21

    close = close.sort_index().dropna(how="all").dropna(axis=1, how="all")
    if close.empty or len(close) < strategy.config.min_history_days + 50:
        return WalkForwardResult(
            guidance=(
                "Insufficient history for walk-forward. Need ~1y+ daily bars. "
                "Check yfinance connectivity or use fixtures."
            ),
            meta={"rows": len(close), "cols": list(close.columns)},
        )

    # Split holdout
    holdout_start = pd.Timestamp(cfg.holdout_start)
    if close.index.tz is not None:
        holdout_start = holdout_start.tz_localize(close.index.tz)
    train_close = close[close.index < holdout_start]
    holdout_close = close[close.index >= holdout_start]

    folds = cfg.walk_forward_folds
    purge = cfg.purge_days
    embargo = cfg.embargo_days
    fold_metrics: list[dict[str, float]] = []
    oos_parts: list[pd.Series] = []

    if len(train_close) > strategy.config.min_history_days + 30:
        # Contiguous expanding walk-forward on pre-holdout
        test_len = max(21, (len(train_close) - strategy.config.min_history_days) // folds)
        for f in range(folds):
            test_end = len(train_close) - (folds - f - 1) * test_len
            test_start = test_end - test_len
            if test_start <= strategy.config.min_history_days:
                continue
            # Purge/embargo: exclude purge days before test from "decision" continuity
            segment = train_close.iloc[: test_end + embargo]
            rets, _ = _simulate_portfolio(
                segment,
                strategy=strategy,
                rebalance_every=rebalance_every,
                fee_bps=cfg.fee_bps,
                slippage_bps=cfg.slippage_bps,
            )
            fold_rets = rets.iloc[test_start + purge : test_end]
            m = performance_metrics(fold_rets, risk_free_rate=cfg.risk_free_rate)
            m["fold"] = float(f)
            fold_metrics.append(m)
            oos_parts.append(fold_rets)

    oos = pd.concat(oos_parts).sort_index() if oos_parts else pd.Series(dtype=float)
    # Deduplicate index if overlapping
    oos = oos[~oos.index.duplicated(keep="first")]
    combined = performance_metrics(oos, risk_free_rate=cfg.risk_free_rate)

    # Holdout (untouched after LLM cutoff date)
    holdout_metrics: dict[str, float] = {}
    buy_hold: dict[str, float] = {}
    if len(holdout_close) > 5:
        # Warm-start with prior history for indicators
        full_for_holdout = close
        rets_full, _ = _simulate_portfolio(
            full_for_holdout,
            strategy=strategy,
            rebalance_every=rebalance_every,
            fee_bps=cfg.fee_bps,
            slippage_bps=cfg.slippage_bps,
        )
        holdout_rets = rets_full.loc[holdout_close.index.intersection(rets_full.index)]
        holdout_metrics = performance_metrics(holdout_rets, risk_free_rate=cfg.risk_free_rate)
        # Buy and hold equal-weight universe (FINSABER-style comparison)
        bh = holdout_close.pct_change().mean(axis=1).dropna()
        buy_hold = performance_metrics(bh, risk_free_rate=cfg.risk_free_rate)

    sharpes = [m.get("sharpe", 0.0) for m in fold_metrics]
    dsr = deflated_sharpe_ratio(
        combined.get("sharpe", 0.0),
        n_obs=int(combined.get("n_obs", 0)),
        n_trials=n_trials_for_dsr,
        sharpe_benchmark=0.0,
    )
    pbo = probabilistic_backtest_overfitting(sharpes, n_strategies=n_trials_for_dsr)

    beats_bh = holdout_metrics.get("sharpe", 0) > buy_hold.get("sharpe", 0)
    guidance_parts = [
        f"Walk-forward folds={len(fold_metrics)}, holdout from {cfg.holdout_start}.",
        f"OOS Sharpe={combined.get('sharpe', 0):.2f}, DSR/PSR={dsr.get('dsr', 0):.2f}, "
        f"PBO proxy={pbo.get('pbo_proxy', 1):.2f}.",
        (
            "Holdout Sharpe "
            f"{holdout_metrics.get('sharpe', float('nan')):.2f} vs buy&hold "
            f"{buy_hold.get('sharpe', float('nan')):.2f} "
            f"({'strategy ahead' if beats_bh else 'buy&hold ahead / inconclusive'})."
        ),
        "Costs applied (fees+slippage). Do not deploy live without paper-trade concordance.",
    ]
    if dsr.get("dsr", 0) < 0.95:
        guidance_parts.append("Deflated Sharpe significance is weak — treat edge as unproven.")
    if pbo.get("pbo_proxy", 1) > 0.4:
        guidance_parts.append(
            "Elevated overfitting proxy — reduce parameter tinkering; prefer simpler rules."
        )

    return WalkForwardResult(
        fold_metrics=fold_metrics,
        oos_returns=oos,
        holdout_metrics=holdout_metrics,
        buy_hold_metrics=buy_hold,
        combined_metrics=combined,
        dsr=dsr,
        pbo=pbo,
        guidance=" ".join(guidance_parts),
        meta={
            "symbols": list(close.columns),
            "start": str(close.index.min()),
            "end": str(close.index.max()),
            "fee_bps": cfg.fee_bps,
            "slippage_bps": cfg.slippage_bps,
            "rebalance_every": rebalance_every,
            "n_trials_for_dsr": n_trials_for_dsr,
        },
    )


def buy_and_hold_benchmark(close: pd.DataFrame) -> dict[str, float]:
    rets = close.pct_change().mean(axis=1).dropna()
    return performance_metrics(rets)
