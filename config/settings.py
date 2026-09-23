from functools import lru_cache
from typing import List, Optional
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
    DATABASE_URL: str = "postgresql://postgres:postgres@postgres:5432/youtube_analytics"
    
    # Security & Auth
    JWT_SECRET: str = "super-secret-jwt-key-change-in-production-1234567890"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ENCRYPTION_SECRET: str = "8vX_8uM_6eN_4rT_2wQ_0zY_9xW_7vU_5sR_3qP_1oN="
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = "8824791628:AAGcvPcC3lCZ3SziCO4fpqVoOhYjEdoudh8"
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = "216e54ccb062bce4dbe9cc9e2eced4d2"
    
    # Default Language (ru, en, de, fi, ka)
    DEFAULT_LANGUAGE: str = "ru"
    
    # Server Host & Port
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8080
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["*"]
    STREAMLIT_SERVER_PORT: int = 8080

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
