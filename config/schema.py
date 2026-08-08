import yaml
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BinanceConfig(BaseSettings):
    mainnet_base_url: str = "https://api.binance.com/api"
    demo_base_url: str = "https://demo-api.binance.com/api"
    api_key: str = ""
    api_secret: str = ""
    recv_window: int = 5000

    model_config = SettingsConfigDict(env_prefix="BINANCE_")


class BacktestConfig(BaseSettings):
    years: int = 3
    start_date: str = "2022-01-01"
    end_date: str = ""
    fee_rate: float = 0.001
    slippage_bps: int = 5

    model_config = SettingsConfigDict(env_prefix="BACKTEST_")


class LiveConfig(BaseSettings):
    alert_missing_candle_hours: int = 6
    reconciliation_tolerance: float = 0.0001

    model_config = SettingsConfigDict(env_prefix="LIVE_")


class Settings(BaseSettings):
    mode: Literal["backtest", "live"] = "backtest"
    symbol: str = "ETHUSDT"
    interval: str = "4h"
    initial_capital: float = 10000.0

    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    live: LiveConfig = Field(default_factory=LiveConfig)

    ema_short: int = 20
    ema_long: int = 50
    atr_period: int = 14
    atr_multiplier: float = 2.0
    risk_per_trade_pct: float = 0.01

    data_dir: str = "./data"
    storage_format: Literal["parquet", "csv", "sqlite"] = "parquet"

    log_level: str = "INFO"
    log_file: str = "./logs/trading.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    @field_validator("data_dir", "log_file", mode="before")
    @classmethod
    def expand_path(cls, v: str) -> str:
        return str(Path(v).expanduser().resolve())

    @field_validator("risk_per_trade_pct")
    @classmethod
    def validate_risk(cls, v: float) -> float:
        if not 0 < v <= 1:
            raise ValueError("risk_per_trade_pct must be between 0 and 1")
        return v

    @field_validator("ema_short", "ema_long", "atr_period")
    @classmethod
    def validate_periods(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Periods must be positive")
        return v

    @field_validator("atr_multiplier")
    @classmethod
    def validate_atr_mult(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("atr_multiplier must be positive")
        return v


def load_settings_from_yaml(yaml_path: str | Path) -> Settings:
    """Load settings from env file (with YAML as reference defaults)."""
    # pydantic-settings automatically loads from env_file specified in model_config
    # The YAML file serves as documentation/defaults; env vars take precedence
    return Settings()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings_from_yaml("config/settings.yaml")
    return _settings


def reload_settings() -> Settings:
    global _settings
    _settings = load_settings_from_yaml("config/settings.yaml")
    return _settings