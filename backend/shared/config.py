"""
Configuration management for FOREX AI Trading Bot.
Loads settings from environment variables and provides typed access.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file="../.env",  # .env is in project root
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    environment: str = Field(default="development", description="Runtime environment")
    log_level: str = Field(default="INFO", description="Logging level")
    debug: bool = Field(default=False, description="Debug mode")

    # OANDA Configuration
    oanda_api_key: str = Field(..., description="OANDA API key")
    oanda_account_id: str = Field(..., description="OANDA account ID")
    oanda_environment: str = Field(
        default="practice", description="OANDA environment (practice or live)"
    )

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field(
        default="gpt-4o-mini", description="OpenAI model to use for analysis"
    )

    # Telegram Configuration
    telegram_bot_token: Optional[str] = Field(default=None, description="Telegram bot token")
    telegram_chat_id: Optional[str] = Field(default=None, description="Telegram chat ID")

    # Database Configuration
    database_url: str = Field(
        default="postgresql://forex_user:forex_pass@localhost:5432/forex_trading",
        description="PostgreSQL connection URL",
    )
    timescaledb_enabled: bool = Field(default=True, description="Enable TimescaleDB features")

    # Redis Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )

    # Streaming Configuration
    streaming_enabled: bool = Field(default=True, description="Enable real-time streaming")
    streaming_instruments: str = Field(
        default="EUR/USD,GBP/USD,USD/JPY",
        description="Instruments to stream (comma-separated)"
    )
    streaming_heartbeat_timeout: int = Field(
        default=10, description="Heartbeat timeout in seconds"
    )

    # Aggregation Configuration
    tick_aggregation_timeframes: str = Field(
        default="M1,M5", description="Timeframes to aggregate ticks into (comma-separated)"
    )

    # AWS Configuration
    aws_region: str = Field(default="us-east-1", description="AWS region")
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS access key")
    aws_secret_access_key: Optional[str] = Field(default=None, description="AWS secret key")
    s3_bucket_models: str = Field(
        default="forex-bot-models", description="S3 bucket for ML models"
    )
    s3_bucket_backtest: str = Field(
        default="forex-bot-backtest", description="S3 bucket for backtest results"
    )

    # Trading Configuration
    trading_pairs: str = Field(
        default="EUR/USD,GBP/USD,USD/JPY", description="Comma-separated trading pairs"
    )
    paper_trading: bool = Field(default=True, description="Paper trading mode")
    initial_capital: float = Field(default=10000.0, description="Initial capital in USD")
    max_positions: int = Field(default=3, description="Maximum concurrent positions")
    risk_per_trade: float = Field(default=0.01, description="Risk per trade (fraction of capital)")
    daily_loss_limit: float = Field(
        default=0.03, description="Daily loss limit (fraction of capital)"
    )

    # ML Configuration
    ml_confidence_threshold: float = Field(
        default=0.65, description="Minimum ML confidence for trading"
    )
    ml_model_version: str = Field(default="v1", description="ML model version")

    # LLM Configuration
    llm_max_calls_per_day: int = Field(
        default=10, description="Maximum ChatGPT API calls per day"
    )
    llm_enable_regime_analysis: bool = Field(
        default=True, description="Enable market regime analysis"
    )
    llm_enable_news_sentiment: bool = Field(
        default=True, description="Enable news sentiment analysis"
    )
    llm_enable_performance_review: bool = Field(
        default=True, description="Enable daily performance review"
    )

    @field_validator("trading_pairs")
    @classmethod
    def parse_trading_pairs(cls, v: str) -> str:
        """Validate trading pairs format."""
        pairs = [p.strip() for p in v.split(",")]
        for pair in pairs:
            if "/" not in pair or len(pair.split("/")) != 2:
                raise ValueError(f"Invalid trading pair format: {pair}")
        return v

    def get_trading_pairs_list(self) -> List[str]:
        """Get trading pairs as a list."""
        return [p.strip() for p in self.trading_pairs.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    @property
    def oanda_base_url(self) -> str:
        """Get OANDA API base URL based on environment."""
        if self.oanda_environment == "live":
            return "https://api-fxtrade.oanda.com"
        return "https://api-fxpractice.oanda.com"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses LRU cache to ensure singleton pattern.
    """
    return Settings()


# Convenience instance for direct import
settings = get_settings()
