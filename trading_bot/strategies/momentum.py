"""Volatility-scaled time-series trend + cross-sectional momentum tilt."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_bot.config.settings import StrategyConfig
from trading_bot.strategies.base import Strategy, TargetPosition
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)

TRADING_DAYS = 252


class VolatilityScaledMomentumStrategy(Strategy):
    """Core strategy from research:

    1. Time-series momentum / trend (primary)
    2. Volatility targeting per name
    3. Cross-sectional momentum tilt among large caps
    4. Optional sentiment size adjust / block (applied here as filter)
    5. Optional ML score blend (advisory weight nudge only)
    """

    name = "volatility_scaled_momentum"

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or StrategyConfig()

    def generate_targets(
        self,
        close: pd.DataFrame,
        *,
        as_of: pd.Timestamp | None = None,
        sentiment: dict[str, float] | None = None,
        ml_scores: dict[str, float] | None = None,
    ) -> list[TargetPosition]:
        if close.empty:
            return []

        close = close.sort_index().dropna(how="all")
        if as_of is not None:
            close = close.loc[:as_of]
        if len(close) < max(self.config.min_history_days // 2, self.config.lookback_days + 5):
            logger.warning(
                "insufficient_history",
                rows=len(close),
                guidance="Need more history before trading; wait or widen download window.",
            )
            return []

        cfg = self.config
        rets = close.pct_change()

        # Time-series momentum: sign of trailing return
        ts_mom = close / close.shift(cfg.lookback_days) - 1.0
        # Longer cross-sectional momentum
        xs_mom = close / close.shift(cfg.momentum_lookback_days) - 1.0

        vol = rets.rolling(cfg.vol_lookback_days).std() * np.sqrt(TRADING_DAYS)
        vol = vol.replace(0, np.nan)

        last_ts = ts_mom.iloc[-1]
        last_xs = xs_mom.iloc[-1]
        last_vol = vol.iloc[-1]

        # Trend sleeve: long assets with positive TS momentum, vol-scaled
        trend_raw: dict[str, float] = {}
        for sym in close.columns:
            m = last_ts.get(sym)
            v = last_vol.get(sym)
            if pd.isna(m) or pd.isna(v) or v <= 0:
                continue
            signal = 1.0 if m > 0 else (-1.0 if cfg.allow_short and m < 0 else 0.0)
            if signal == 0.0:
                continue
            # volatility scale toward target
            scale = float(cfg.vol_target_annual / v)
            scale = float(np.clip(scale, 0.1, 2.0))
            trend_raw[sym] = signal * scale

        # Normalize trend sleeve
        trend_weights = _normalize_long(trend_raw, cfg.trend_weight)

        # Cross-sectional tilt: top N by XS momentum among those with data
        xs_ranked = last_xs.dropna().sort_values(ascending=False)
        top = list(xs_ranked.head(cfg.cross_sectional_top_n).index)
        xs_raw = {sym: 1.0 for sym in top if last_xs.get(sym, -np.inf) > 0}
        xs_weights = _normalize_long(xs_raw, cfg.cross_sectional_weight)

        # Blend
        symbols = set(trend_weights) | set(xs_weights)
        blended: dict[str, float] = {}
        for sym in symbols:
            blended[sym] = trend_weights.get(sym, 0.0) + xs_weights.get(sym, 0.0)

        # Optional ML nudge (±10% relative)
        if ml_scores:
            for sym, w in list(blended.items()):
                score = ml_scores.get(sym)
                if score is None:
                    continue
                # score expected ~[-1, 1]
                blended[sym] = w * (1.0 + 0.10 * float(np.clip(score, -1, 1)))

        # Sentiment filter / tilt
        sentiment = sentiment or {}
        targets: list[TargetPosition] = []
        for sym, weight in sorted(blended.items(), key=lambda x: -x[1]):
            sent = sentiment.get(sym)
            blocked = False
            block_reason = ""
            reason_parts = []
            ts_v = float(last_ts.get(sym)) if not pd.isna(last_ts.get(sym)) else 0.0
            xs_v = float(last_xs.get(sym)) if not pd.isna(last_xs.get(sym)) else 0.0
            vol_v = float(last_vol.get(sym)) if not pd.isna(last_vol.get(sym)) else 0.0
            reason_parts.append(f"ts_mom={ts_v:.3f}")
            reason_parts.append(f"xs_mom={xs_v:.3f}")
            reason_parts.append(f"vol={vol_v:.3f}")
            if sym in trend_weights:
                reason_parts.append(f"trend_w={trend_weights[sym]:.3f}")
            if sym in xs_weights:
                reason_parts.append(f"xs_w={xs_weights[sym]:.3f}")

            if sent is not None:
                reason_parts.append(f"sentiment={sent:.3f}")
                # block new entries on strongly negative (weight → 0)
                # (exits still handled by absence from targets / risk stops)
                if sent <= -0.55 and weight > 0:
                    blocked = True
                    block_reason = (
                        f"News sentiment {sent:.2f} below block threshold; "
                        "entry blocked (risk rules still govern exits)."
                    )
                    weight = 0.0
                elif sent >= 0.45 and weight > 0:
                    weight *= 1.15
                    reason_parts.append("sentiment_boost")

            targets.append(
                TargetPosition(
                    symbol=sym,
                    weight=float(max(weight, 0.0)),
                    reason="; ".join(reason_parts),
                    blocked=blocked,
                    block_reason=block_reason,
                    sentiment_score=sent,
                    metadata={
                        "ts_momentum": ts_v,
                        "xs_momentum": xs_v,
                        "volatility": vol_v,
                    },
                )
            )

        # Final gross exposure clip
        gross = sum(t.weight for t in targets)
        if gross > 1.0 and gross > 0:
            for t in targets:
                t.weight /= gross

        return targets


def _normalize_long(raw: dict[str, float], sleeve_weight: float) -> dict[str, float]:
    positives = {k: max(v, 0.0) for k, v in raw.items() if v > 0}
    total = sum(positives.values())
    if total <= 0:
        return {}
    return {k: sleeve_weight * (v / total) for k, v in positives.items()}
