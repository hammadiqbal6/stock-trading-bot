"""Optional gradient-boosting model on TA features — walk-forward retrain only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from trading_bot.config.settings import MLConfig
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


def build_feature_frame(close: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    """Build per-symbol panel of technical features (stacked long format)."""
    try:
        import ta
    except ImportError:
        ta = None  # type: ignore[assignment]

    frames: list[pd.DataFrame] = []
    for sym in close.columns:
        s = close[sym].dropna()
        if len(s) < max(windows) + 5:
            continue
        feat = pd.DataFrame(index=s.index)
        rets = s.pct_change()
        for w in windows:
            feat[f"ret_{w}"] = s.pct_change(w)
            feat[f"vol_{w}"] = rets.rolling(w).std()
            feat[f"z_{w}"] = (s - s.rolling(w).mean()) / s.rolling(w).std()
        if ta is not None:
            try:
                feat["rsi_14"] = ta.momentum.RSIIndicator(s, window=14).rsi()
                # MACD needs more series — use close only helper
                macd = ta.trend.MACD(s)
                feat["macd"] = macd.macd_diff()
            except Exception:
                pass
        feat["symbol"] = sym
        feat["fwd_ret"] = s.pct_change().shift(-1)
        frames.append(feat)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames).dropna()


@dataclass
class WalkForwardML:
    config: MLConfig
    model: Any | None = None
    last_train_end: pd.Timestamp | None = None

    def fit_predict_scores(
        self,
        close: pd.DataFrame,
        *,
        as_of: pd.Timestamp | None = None,
    ) -> dict[str, float]:
        if not self.config.enabled:
            return {}
        data = close if as_of is None else close.loc[:as_of]
        feats = build_feature_frame(data, self.config.feature_windows)
        if feats.empty or len(feats) < 500:
            logger.warning(
                "ml_insufficient_features",
                rows=len(feats),
                guidance="Need more history before enabling ML sleeve.",
            )
            return {}

        feature_cols = [c for c in feats.columns if c not in {"symbol", "fwd_ret"}]
        # Walk-forward: train on all but last test window ending at as_of
        dates = feats.index.unique().sort_values()
        if len(dates) < self.config.walk_forward_train_days:
            return {}
        train_end_idx = max(len(dates) - self.config.walk_forward_test_days, 1)
        train_dates = set(dates[:train_end_idx])
        train = feats[feats.index.isin(train_dates)]
        latest_date = dates[-1]
        latest = feats[feats.index == latest_date]

        X_train = train[feature_cols].to_numpy()
        y_train = np.sign(train["fwd_ret"].to_numpy())
        # Map -1/0/1 — drop zeros for classifier stability
        mask = y_train != 0
        X_train, y_train = X_train[mask], y_train[mask]
        if len(y_train) < 200:
            return {}

        model = self._make_model()
        try:
            model.fit(X_train, y_train)
        except Exception as exc:
            logger.warning("ml_fit_failed", error=str(exc))
            return {}
        self.model = model
        self.last_train_end = dates[train_end_idx - 1]

        if latest.empty:
            return {}
        X_latest = latest[feature_cols].to_numpy()
        try:
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(X_latest)
                # positive class probability mapped to [-1,1]
                classes = list(model.classes_)
                if 1 in classes or 1.0 in classes:
                    idx = classes.index(1) if 1 in classes else classes.index(1.0)
                    scores = proba[:, idx] * 2 - 1
                else:
                    scores = model.predict(X_latest).astype(float)
            else:
                scores = model.predict(X_latest).astype(float)
        except Exception as exc:
            logger.warning("ml_predict_failed", error=str(exc))
            return {}

        out: dict[str, float] = {}
        for sym, score in zip(latest["symbol"].tolist(), scores, strict=False):
            out[str(sym)] = float(np.clip(score, -1, 1))
        return out

    def _make_model(self) -> Any:
        if self.config.model == "xgboost":
            try:
                from xgboost import XGBClassifier

                return XGBClassifier(
                    n_estimators=80,
                    max_depth=3,
                    learning_rate=0.05,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    objective="binary:logistic",
                    eval_metric="logloss",
                    verbosity=0,
                )
            except Exception:
                logger.warning("xgboost_unavailable_using_sklearn")
        from sklearn.ensemble import GradientBoostingClassifier

        return GradientBoostingClassifier(random_state=42)
