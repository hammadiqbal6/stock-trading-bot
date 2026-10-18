"""Pydantic settings with YAML defaults and env overrides."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"
    DRY_RUN = "dry_run"


class LLMProvider(str, Enum):
    NONE = "none"
    GROQ = "groq"
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"


class BrokerName(str, Enum):
    ALPACA = "alpaca"
    IBKR = "ibkr"
    PAPER_SIM = "paper_sim"


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_YAML = ROOT_DIR / "config" / "settings.yaml"


class UniverseConfig(BaseModel):
    etfs: list[str] = Field(default_factory=lambda: ["SPY", "QQQ", "IWM", "TLT", "GLD"])
    large_caps: list[str] = Field(
        default_factory=lambda: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
    )

    @property
    def all_symbols(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for s in self.etfs + self.large_caps:
            u = s.upper().strip()
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        return out


class StrategyConfig(BaseModel):
    name: str = "volatility_scaled_momentum"
    rebalance: Literal["weekly", "monthly"] = "weekly"
    lookback_days: int = 63
    momentum_lookback_days: int = 126
    vol_lookback_days: int = 21
    vol_target_annual: float = 0.12
    cross_sectional_top_n: int = 8
    cross_sectional_weight: float = 0.30
    trend_weight: float = 0.70
    min_history_days: int = 252
    allow_short: bool = False


class SentimentConfig(BaseModel):
    enabled: bool = True
    lookback_hours: int = 48
    block_threshold: float = -0.55
    boost_threshold: float = 0.45
    boost_factor: float = 1.15
    cache_ttl_hours: int = 6
    anonymise_entities: bool = True
    fallback: Literal["finbert", "neutral"] = "finbert"


class MLConfig(BaseModel):
    enabled: bool = False
    model: Literal["xgboost", "sklearn_gbm"] = "xgboost"
    retrain_every_days: int = 21
    walk_forward_train_days: int = 504
    walk_forward_test_days: int = 63
    feature_windows: list[int] = Field(default_factory=lambda: [5, 10, 21, 63])


class RiskConfig(BaseModel):
    max_position_pct: float = 0.10
    max_gross_exposure: float = 1.0
    daily_loss_cap_pct: float = 0.02
    max_drawdown_pct: float = 0.15
    stop_loss_pct: float = 0.08
    kill_switch_enabled: bool = True
    pdt_aware: bool = True
    min_equity_for_day_trades: float = 25_000.0
    fractional_shares: bool = True
    min_order_notional: float = 1.0


class ExecutionConfig(BaseModel):
    broker: BrokerName = BrokerName.ALPACA
    order_type: Literal["market", "limit"] = "market"
    time_in_force: Literal["day", "gtc", "ioc"] = "day"
    slippage_bps: float = 5.0
    commission_bps: float = 0.0
    submit_during_regular_hours_only: bool = True


class ValidationConfig(BaseModel):
    walk_forward_folds: int = 5
    purge_days: int = 5
    embargo_days: int = 2
    holdout_start: str = "2024-07-01"
    fee_bps: float = 5.0
    slippage_bps: float = 5.0
    risk_free_rate: float = 0.04
    target_sharpe: float = 0.5


class AdvisoryConfig(BaseModel):
    enabled: bool = False
    never_place_orders: bool = True
    never_override_risk: bool = True
    agents: list[str] = Field(
        default_factory=lambda: ["fundamental", "sentiment", "technical", "risk"]
    )
    cache_ttl_hours: int = 24

    @model_validator(mode="after")
    def enforce_safety(self) -> AdvisoryConfig:
        # Hard invariants — advisory layer must never trade or override risk
        object.__setattr__(self, "never_place_orders", True)
        object.__setattr__(self, "never_override_risk", True)
        return self


class SchedulerConfig(BaseModel):
    timezone: str = "America/New_York"
    pre_market_check: str = "09:00"
    rebalance_day: str = "mon"
    sentiment_refresh_minutes: int = 30
    health_check_minutes: int = 5


class DataConfig(BaseModel):
    primary: Literal["alpaca", "yfinance"] = "alpaca"
    historical_backtest: Literal["yfinance", "alpaca"] = "yfinance"
    bar_size: str = "1Day"
    adjust_splits: bool = True
    adjust_dividends: bool = True


class YamlBundle(BaseModel):
    universe: UniverseConfig = Field(default_factory=UniverseConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    sentiment: SentimentConfig = Field(default_factory=SentimentConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    advisory: AdvisoryConfig = Field(default_factory=AdvisoryConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    data: DataConfig = Field(default_factory=DataConfig)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        msg = f"Config YAML must be a mapping: {path}"
        raise ValueError(msg)
    return data


class Settings(BaseSettings):
    """Runtime settings: env + .env override YAML defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: SecretStr = SecretStr("dev-only-change-me")
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    trading_mode: TradingMode = TradingMode.PAPER
    live_trading_enabled: bool = False
    live_trading_confirm: str = ""

    alpaca_api_key: SecretStr = SecretStr("")
    alpaca_secret_key: SecretStr = SecretStr("")
    alpaca_paper: bool = True
    alpaca_data_feed: str = "iex"

    finnhub_api_key: SecretStr = SecretStr("")

    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "llama-3.1-8b-instant"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    llm_provider: LLMProvider = LLMProvider.NONE
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    max_position_pct: float | None = None
    daily_loss_cap_pct: float | None = None
    max_drawdown_pct: float | None = None
    vol_target_annual: float | None = None

    data_dir: Path = Path("./data")
    cache_dir: Path = Path("./data/cache")
    model_dir: Path = Path("./data/models")
    log_dir: Path = Path("./logs")

    enable_ml_model: bool | None = None
    enable_news_sentiment: bool | None = None
    enable_trading_agents_advisory: bool | None = None
    enable_scheduler: bool = True

    config_yaml: Path = DEFAULT_YAML

    # Populated after init from YAML + env overlays
    yaml: YamlBundle = Field(default_factory=YamlBundle)

    @field_validator("trading_mode", mode="before")
    @classmethod
    def _parse_mode(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower().strip()
        return v

    @model_validator(mode="after")
    def _merge_yaml_and_guards(self) -> Settings:
        raw = _load_yaml(self.config_yaml)
        # Drop app wrapper keys not in YamlBundle
        filtered = {k: v for k, v in raw.items() if k in YamlBundle.model_fields}
        bundle = YamlBundle.model_validate(filtered)

        # Env overlays for risk / feature flags
        if self.max_position_pct is not None:
            bundle.risk.max_position_pct = self.max_position_pct
        if self.daily_loss_cap_pct is not None:
            bundle.risk.daily_loss_cap_pct = self.daily_loss_cap_pct
        if self.max_drawdown_pct is not None:
            bundle.risk.max_drawdown_pct = self.max_drawdown_pct
        if self.vol_target_annual is not None:
            bundle.strategy.vol_target_annual = self.vol_target_annual
        if self.enable_ml_model is not None:
            bundle.ml.enabled = self.enable_ml_model
        if self.enable_news_sentiment is not None:
            bundle.sentiment.enabled = self.enable_news_sentiment
        if self.enable_trading_agents_advisory is not None:
            bundle.advisory.enabled = self.enable_trading_agents_advisory

        # Live trading hard gate
        if self.trading_mode == TradingMode.LIVE:
            if not self.live_trading_enabled:
                msg = (
                    "LIVE trading requested but LIVE_TRADING_ENABLED is false. "
                    "Set LIVE_TRADING_ENABLED=true and LIVE_TRADING_CONFIRM=I_UNDERSTAND_THE_RISKS."
                )
                raise ValueError(msg)
            if self.live_trading_confirm != "I_UNDERSTAND_THE_RISKS":
                msg = (
                    "LIVE trading requires LIVE_TRADING_CONFIRM=I_UNDERSTAND_THE_RISKS. "
                    "Paper trading is the default and recommended mode."
                )
                raise ValueError(msg)
            if self.alpaca_paper:
                msg = (
                    "LIVE mode with ALPACA_PAPER=true is inconsistent. "
                    "Set ALPACA_PAPER=false only after confirming live credentials."
                )
                raise ValueError(msg)

        # Paper safety: force paper API when not live
        if self.trading_mode != TradingMode.LIVE:
            object.__setattr__(self, "alpaca_paper", True)

        object.__setattr__(self, "yaml", bundle)

        for d in (self.data_dir, self.cache_dir, self.model_dir, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)

        return self

    def has_alpaca_credentials(self) -> bool:
        return bool(
            self.alpaca_api_key.get_secret_value().strip()
            and self.alpaca_secret_key.get_secret_value().strip()
        )

    def has_finnhub(self) -> bool:
        return bool(self.finnhub_api_key.get_secret_value().strip())

    def has_groq(self) -> bool:
        return bool(self.groq_api_key.get_secret_value().strip())

    def setup_status(self) -> dict[str, Any]:
        """Actionable onboarding status for the UI wizard."""
        return {
            "trading_mode": self.trading_mode.value,
            "alpaca": {
                "configured": self.has_alpaca_credentials(),
                "paper": self.alpaca_paper,
                "required": True,
                "guidance": (
                    "Create a free Alpaca paper account at https://app.alpaca.markets/signup "
                    "and set ALPACA_API_KEY / ALPACA_SECRET_KEY. Paper accounts are open worldwide "
                    "(including Pakistan)."
                    if not self.has_alpaca_credentials()
                    else "Alpaca credentials present."
                ),
            },
            "finnhub": {
                "configured": self.has_finnhub(),
                "required": False,
                "guidance": (
                    "Optional: register at https://finnhub.io/register for company news "
                    "(free 60 req/min). Without it, GDELT-only news is used."
                    if not self.has_finnhub()
                    else "Finnhub key present."
                ),
            },
            "llm": {
                "provider": self.llm_provider.value,
                "configured": (
                    self.llm_provider == LLMProvider.NONE
                    or (
                        self.llm_provider == LLMProvider.GROQ and self.has_groq()
                    )
                    or self.llm_provider == LLMProvider.OLLAMA
                    or (
                        self.llm_provider == LLMProvider.OPENAI_COMPATIBLE
                        and bool(self.openai_api_key.get_secret_value().strip())
                    )
                ),
                "required": False,
                "guidance": (
                    "LLM is optional. FinBERT runs locally with no key. "
                    "For Groq free tier: https://console.groq.com/keys"
                ),
            },
            "gdelt": {
                "configured": True,
                "required": False,
                "guidance": "GDELT requires no signup or API key.",
            },
            "finbert": {
                "configured": True,
                "required": False,
                "guidance": "FinBERT runs locally (first download may take a minute).",
            },
            "live_gate": {
                "enabled": self.live_trading_enabled,
                "confirmed": self.live_trading_confirm == "I_UNDERSTAND_THE_RISKS",
                "guidance": "Live trading is OFF by default and requires two explicit env flags.",
            },
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
