"""Market data: Alpaca (live/paper IEX) + yfinance (historical backtests)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from trading_bot.config.settings import Settings, get_settings
from trading_bot.utils.exceptions import DataError, MissingCredentialsError
from trading_bot.utils.logging import get_logger
from trading_bot.utils.rate_limit import RateLimiter

logger = get_logger(__name__)


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def get_bars(
        self,
        symbols: list[str],
        *,
        start: datetime | str,
        end: datetime | str | None = None,
        timeframe: str = "1Day",
    ) -> pd.DataFrame:
        """Return OHLCV MultiIndex (symbol, timestamp) or wide close panel.

        Standard output: DataFrame indexed by DatetimeIndex with columns MultiIndex
        (field, symbol) where field in open/high/low/close/volume — or a simple
        close-price panel with symbols as columns when `close_only` helpers used.
        """
        ...

    def get_close_panel(
        self,
        symbols: list[str],
        *,
        start: datetime | str,
        end: datetime | str | None = None,
    ) -> pd.DataFrame:
        bars = self.get_bars(symbols, start=start, end=end)
        if isinstance(bars.columns, pd.MultiIndex) and "close" in bars.columns.get_level_values(0):
            return bars["close"].sort_index()
        # assume already close panel
        return bars.sort_index()

    @abstractmethod
    def health_check(self) -> dict[str, Any]: ...


class YFinanceProvider(MarketDataProvider):
    """Historical data for backtests only (not for live decisioning latency)."""

    name = "yfinance"

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir
        self._limiter = RateLimiter(rate=2.0, capacity=5, name="yfinance")

    def get_bars(
        self,
        symbols: list[str],
        *,
        start: datetime | str,
        end: datetime | str | None = None,
        timeframe: str = "1Day",
    ) -> pd.DataFrame:
        if timeframe not in {"1Day", "1d", "day"}:
            raise DataError(
                f"yfinance provider supports daily bars only (got {timeframe})",
                guidance="Use timeframe=1Day for backtests, or Alpaca for intraday.",
            )
        try:
            import yfinance as yf
        except ImportError as exc:
            raise DataError(
                "yfinance not installed",
                guidance="pip install -e .",
            ) from exc

        syms = [s.upper().strip() for s in symbols]
        if not syms:
            raise DataError("No symbols requested", guidance="Provide at least one ticker.")

        self._limiter.acquire()
        try:
            data = yf.download(
                syms,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                threads=True,
                group_by="ticker",
            )
        except Exception as exc:
            raise DataError(
                f"yfinance download failed: {exc}",
                guidance=(
                    "Check network access to Yahoo Finance. If rate-limited, wait and retry. "
                    "For CI/offline, use tests/fixtures sample parquet."
                ),
            ) from exc

        if data is None or data.empty:
            raise DataError(
                "yfinance returned empty data",
                guidance="Verify symbols and date range. Some tickers may be delisted.",
            )

        return _normalize_yfinance(data, syms)

    def health_check(self) -> dict[str, Any]:
        try:
            panel = self.get_close_panel(["SPY"], start="2024-01-02", end="2024-01-10")
            ok = not panel.empty
            return {
                "ok": ok,
                "provider": self.name,
                "rows": len(panel),
                "guidance": "yfinance reachable." if ok else "Empty response from yfinance.",
            }
        except Exception as exc:
            return {
                "ok": False,
                "provider": self.name,
                "error": str(exc),
                "guidance": "Cannot reach Yahoo Finance. Backtests need network or fixtures.",
            }


class AlpacaDataProvider(MarketDataProvider):
    """Alpaca Market Data Basic (IEX)."""

    name = "alpaca"

    def __init__(self, settings: Settings) -> None:
        if not settings.has_alpaca_credentials():
            raise MissingCredentialsError(
                "Alpaca Market Data",
                guidance=(
                    "Set ALPACA_API_KEY and ALPACA_SECRET_KEY. "
                    "Basic plan includes IEX realtime and SIP 15-min delayed."
                ),
            )
        from alpaca.data.historical import StockHistoricalDataClient

        self._settings = settings
        self._client = StockHistoricalDataClient(
            api_key=settings.alpaca_api_key.get_secret_value(),
            secret_key=settings.alpaca_secret_key.get_secret_value(),
        )
        # Basic plan ~200 calls/min
        self._limiter = RateLimiter(rate=3.0, capacity=10, name="alpaca_data")

    def get_bars(
        self,
        symbols: list[str],
        *,
        start: datetime | str,
        end: datetime | str | None = None,
        timeframe: str = "1Day",
    ) -> pd.DataFrame:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        tf_map = {
            "1Day": TimeFrame.Day,
            "1d": TimeFrame.Day,
            "day": TimeFrame.Day,
            "1Hour": TimeFrame.Hour,
            "1Min": TimeFrame.Minute,
        }
        tf = tf_map.get(timeframe, TimeFrame.Day)
        syms = [s.upper().strip() for s in symbols]
        self._limiter.acquire()
        try:
            req = StockBarsRequest(
                symbol_or_symbols=syms,
                timeframe=tf,
                start=start,
                end=end,
                feed=self._settings.alpaca_data_feed,
            )
            bars = self._client.get_stock_bars(req)
            df = bars.df
        except Exception as exc:
            raise DataError(
                f"Alpaca bars failed: {exc}",
                guidance=(
                    "Check keys, feed (iex), and rate limits (200/min Basic). "
                    "Fall back to yfinance for historical backtests."
                ),
            ) from exc

        if df is None or df.empty:
            raise DataError(
                "Alpaca returned empty bars",
                guidance="Symbol may be unsupported on IEX feed or date range has no sessions.",
            )
        return _normalize_alpaca(df)

    def health_check(self) -> dict[str, Any]:
        try:
            panel = self.get_close_panel(["SPY"], start="2024-01-02", end="2024-01-10")
            return {
                "ok": not panel.empty,
                "provider": self.name,
                "feed": self._settings.alpaca_data_feed,
                "guidance": "Alpaca market data reachable.",
            }
        except Exception as exc:
            return {
                "ok": False,
                "provider": self.name,
                "error": str(exc),
                "guidance": "Alpaca data unreachable — verify keys / network.",
            }


def _normalize_yfinance(data: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """Return MultiIndex columns (field, symbol)."""
    fields = ["Open", "High", "Low", "Close", "Volume"]
    if len(symbols) == 1 and not isinstance(data.columns, pd.MultiIndex):
        sym = symbols[0]
        frames = {}
        for f in fields:
            if f in data.columns:
                frames[(f.lower(), sym)] = data[f]
        out = pd.DataFrame(frames)
        out.columns = pd.MultiIndex.from_tuples(out.columns)
        return out.dropna(how="all")

    # Multi-ticker: columns (ticker, field) from yfinance group_by=ticker
    pieces: dict[tuple[str, str], pd.Series] = {}
    if isinstance(data.columns, pd.MultiIndex):
        # Could be (ticker, field) or (field, ticker)
        level0 = data.columns.get_level_values(0)
        if any(f in set(level0) for f in fields):
            # (field, ticker)
            for f in fields:
                if f in data.columns.get_level_values(0):
                    sub = data[f]
                    for sym in sub.columns:
                        pieces[(f.lower(), str(sym).upper())] = sub[sym]
        else:
            for sym in symbols:
                if sym not in data.columns.get_level_values(0):
                    continue
                sub = data[sym]
                for f in fields:
                    if f in sub.columns:
                        pieces[(f.lower(), sym)] = sub[f]
    out = pd.DataFrame(pieces)
    if not out.empty:
        out.columns = pd.MultiIndex.from_tuples(out.columns)
    return out.dropna(how="all")


def _normalize_alpaca(df: pd.DataFrame) -> pd.DataFrame:
    """Alpaca bars.df typically MultiIndex (symbol, timestamp) with ohlcv columns."""
    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index()
    # expect columns: symbol, timestamp, open, high, low, close, volume
    cols = {c.lower(): c for c in df.columns}
    symbol_col = cols.get("symbol")
    ts_col = cols.get("timestamp") or cols.get("time")
    if symbol_col is None or ts_col is None:
        raise DataError(
            "Unexpected Alpaca bars schema",
            guidance=f"Columns were: {list(df.columns)}",
        )
    df = df.copy()
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
    pieces: dict[tuple[str, str], pd.Series] = {}
    for sym, grp in df.groupby(symbol_col):
        g = grp.set_index(ts_col).sort_index()
        for f in ("open", "high", "low", "close", "volume"):
            src = cols.get(f)
            if src and src in g.columns:
                pieces[(f, str(sym).upper())] = g[src]
    out = pd.DataFrame(pieces)
    out.columns = pd.MultiIndex.from_tuples(out.columns)
    return out


def get_data_provider(
    settings: Settings | None = None,
    *,
    purpose: Literal["live", "backtest"] = "live",
) -> MarketDataProvider:
    settings = settings or get_settings()
    if purpose == "backtest":
        return YFinanceProvider(cache_dir=settings.cache_dir)
    if settings.yaml.data.primary == "alpaca" and settings.has_alpaca_credentials():
        return AlpacaDataProvider(settings)
    logger.warning(
        "using_yfinance_for_live_data",
        guidance="Alpaca keys missing — using yfinance (OK for demos, not for low-latency live).",
    )
    return YFinanceProvider(cache_dir=settings.cache_dir)
