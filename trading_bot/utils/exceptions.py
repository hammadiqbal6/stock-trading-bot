"""Domain exceptions with actionable guidance for UI and logs."""

from __future__ import annotations


class TradingBotError(Exception):
    """Base error with user-facing guidance."""

    def __init__(self, message: str, *, guidance: str = "", code: str = "error") -> None:
        super().__init__(message)
        self.message = message
        self.guidance = guidance or message
        self.code = code

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "guidance": self.guidance}


class ConfigError(TradingBotError):
    def __init__(self, message: str, *, guidance: str = "") -> None:
        super().__init__(message, guidance=guidance, code="config_error")


class MissingCredentialsError(TradingBotError):
    def __init__(self, service: str, *, guidance: str) -> None:
        super().__init__(
            f"Missing credentials for {service}",
            guidance=guidance,
            code="missing_credentials",
        )
        self.service = service


class BrokerError(TradingBotError):
    def __init__(self, message: str, *, guidance: str = "") -> None:
        super().__init__(message, guidance=guidance, code="broker_error")


class MarketClosedError(TradingBotError):
    def __init__(self, message: str = "US equity market is closed", *, next_open: str = "") -> None:
        guidance = (
            f"Market is closed. Next regular open: {next_open}. "
            "Orders are queued for the next session when submit_during_regular_hours_only=true."
            if next_open
            else "Market is closed. Check the NYSE calendar / holiday schedule."
        )
        super().__init__(message, guidance=guidance, code="market_closed")
        self.next_open = next_open


class InsufficientBuyingPowerError(TradingBotError):
    def __init__(self, required: float, available: float) -> None:
        super().__init__(
            f"Insufficient buying power: need ${required:.2f}, have ${available:.2f}",
            guidance=(
                "Reduce position size, deposit paper funds (Alpaca paper UI), "
                "or wait for unsettled cash. Fractional shares may lower the minimum notional."
            ),
            code="insufficient_buying_power",
        )


class PDTRestrictionError(TradingBotError):
    def __init__(self, day_trades_used: int, equity: float) -> None:
        super().__init__(
            f"PDT rule would be violated ({day_trades_used} day trades, equity ${equity:.0f})",
            guidance=(
                "Accounts under $25,000 are limited to 3 day trades in 5 business days. "
                "Prefer swing/weekly rebalances, or use Alpaca paper (PDT still simulated) carefully. "
                "Raise equity above $25k or wait for the rolling window to clear."
            ),
            code="pdt_restriction",
        )


class RiskKillSwitchError(TradingBotError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            f"Risk kill switch engaged: {reason}",
            guidance=(
                "Trading is halted. Review drawdown / daily loss in the dashboard Risk panel. "
                "Reset only after investigating; kill switch does not auto-clear."
            ),
            code="kill_switch",
        )


class DataError(TradingBotError):
    def __init__(self, message: str, *, guidance: str = "") -> None:
        super().__init__(
            message,
            guidance=guidance
            or (
                "Check symbol validity, network connectivity, and API rate limits. "
                "Historical backtests can fall back to yfinance."
            ),
            code="data_error",
        )


class LLMProviderError(TradingBotError):
    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(
            f"LLM provider '{provider}' failed: {detail}",
            guidance=(
                "Falling back to local FinBERT / neutral sentiment. "
                "Check API key, rate limits, or switch LLM_PROVIDER=none|ollama."
            ),
            code="llm_provider_error",
        )


class PartialFillError(TradingBotError):
    def __init__(self, symbol: str, filled: float, requested: float) -> None:
        super().__init__(
            f"Partial fill for {symbol}: {filled}/{requested}",
            guidance=(
                "Partial fills are tracked; residual qty may be resubmitted next cycle "
                "if still within risk limits and market hours."
            ),
            code="partial_fill",
        )
