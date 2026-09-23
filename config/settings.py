from functools import lru_cache
from typing import List, Optional
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "YouTube Analytics Platform"
    DEBUG: bool = False
    
    # Domains & Routing (Dokploy Traefik)
    DASHBOARD_URL: str = "https://yap.oxyjet.win"
    BACKEND_PUBLIC_URL: str = "https://api.yap.oxyjet.win"
    DOKPLOY_WEB_DOMAIN: str = "yap.oxyjet.win"
    DOKPLOY_API_DOMAIN: str = "api.yap.oxyjet.win"
    BACKEND_API_URL: str = "http://backend:8080/api/v1"
    SANDBOX_SERVICE_URL: str = "http://sandbox:8080"
    
    # Database (PostgreSQL with SQLite fallback)
    DATABASE_URL: str = "postgresql://yap_user:yap_secure_pass_2026@postgres:5432/youtube_analytics"
    
    # Security & Auth (Supports both JWT_SECRET/SECRET_KEY and ENCRYPTION_SECRET/ENCRYPTION_KEY)
    JWT_SECRET: str = Field(
        default="change-in-production-jwt-secret-key-32chars-min",
        validation_alias=AliasChoices("JWT_SECRET", "SECRET_KEY")
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ENCRYPTION_SECRET: str = Field(
        default="8vX_8uM_6eN_4rT_2wQ_0zY_9xW_7vU_5sR_3qP_1oN=",
        validation_alias=AliasChoices("ENCRYPTION_SECRET", "ENCRYPTION_KEY")
    )
    ADMIN_SECRET: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ADMIN_SECRET", "ADMIN_KEY")
    )
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_BOT_USERNAME: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None
    CRON_SECRET: Optional[str] = None
    
    # Default Language (ru, en, de, fi, ka)
    DEFAULT_LANGUAGE: str = "ru"
    
    # Server Host & Port
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8080
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = [
        "https://yap.oxyjet.win",
        "https://api.yap.oxyjet.win",
        "http://localhost:8501",
        "http://localhost:8000"
    ]
    STREAMLIT_SERVER_PORT: int = 8080

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()

