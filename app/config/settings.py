import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # AI / LLM Configuration
    OPENROUTER_API_KEY: str = "mock_key"
    OPENROUTER_MODEL: str = "google/gemma-2-9b-it:free"
    OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1/chat/completions"
    PRIMARY_MODEL: str = "google/gemma-2-9b-it:free"
    FALLBACK_MODELS: str = "meta-llama/llama-3-8b-instruct:free,mistralai/mistral-7b-instruct:free"

    # Telegram Bot Settings
    TELEGRAM_BOT_TOKEN: str = "mock_bot_token"
    TELEGRAM_ADMIN_ID: int = 7669464229
    ADMIN_BOT_TOKEN: Optional[str] = None

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///data/sponsor.db"

    # Autonomous Pipeline & Scheduler
    CHECK_INTERVAL_MINUTES: int = 60
    MAX_SPONSORS_PER_RUN: int = 25
    SCORE_THRESHOLD: int = 70
    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = "Asia/Jakarta"
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    # Dual-Port VPS Networking & Admin Dashboard
    BOT_PORT: int = 20138
    WEB_PORT: int = 20139
    HOST: str = "0.0.0.0"
    WEB_BASE_URL: str = "http://localhost:20139"
    ADMIN_PASSWORD: str = "uranium235aregoated"
    SESSION_SECRET_KEY: str = "sponsor-finder-secret-key-uranium235"

    # Google SSO & Gmail OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:20139/auth/google/callback"

    # Search Configuration
    SEARCH_REGIONS: str = "Indonesia,Global"
    SEARCH_CATEGORIES: str = "Tech,FMCG,Banking,Telco,Gaming,Beverage,Fashion,EdTech,CSR"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def fallback_models_list(self) -> List[str]:
        if not self.FALLBACK_MODELS:
            return []
        return [m.strip() for m in self.FALLBACK_MODELS.split(",") if m.strip()]

    @property
    def regions_list(self) -> List[str]:
        return [r.strip() for r in self.SEARCH_REGIONS.split(",") if r.strip()]

    @property
    def categories_list(self) -> List[str]:
        return [c.strip() for c in self.SEARCH_CATEGORIES.split(",") if c.strip()]

settings = Settings()
