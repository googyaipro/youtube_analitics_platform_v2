from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "YouTube Analytics Platform"
    DEBUG: bool = False
    
    # YouTube Data API
    YOUTUBE_API_KEY: Optional[str] = None
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = "secret-tg-token-xyz"
    
    # Google Cloud Platform
    GCP_PROJECT_ID: str = "agentverse-guardian-gcloud"
    GCP_LOCATION: str = "US"
    GCP_REGION: str = "us-central1"
    BIGQUERY_DATASET_ID: str = "youtube_analytics"
    GCS_BUCKET_NAME: str = "youtube-analytics-raw-data-bucket"
    CLOUD_TASKS_QUEUE: str = "telegram-tasks"
    
    # Microservices URLs
    SANDBOX_SERVICE_URL: str = "http://localhost:8080"
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    
    # AI / Vertex AI
    GEMINI_MODEL: str = "gemini-2.0-flash"
    
    # Backend Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    API_V1_PREFIX: str = "/api"
    CORS_ORIGINS: List[str] = ["*"]
    
    # Dashboard config
    BACKEND_API_URL: str = "http://localhost:8000/api"
    STREAMLIT_SERVER_PORT: int = 8501

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
