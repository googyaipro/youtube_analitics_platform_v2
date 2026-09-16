from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App config
    APP_NAME: str = "YouTube Analytics Platform"
    DEBUG: bool = False
    
    # YouTube Data API
    YOUTUBE_API_KEY: Optional[str] = None
    
    # Google Cloud Platform
    GCP_PROJECT_ID: str = "agentverse-guardian-gcloud"
    GCP_LOCATION: str = "US"
    BIGQUERY_DATASET_ID: str = "youtube_analytics"
    GCS_BUCKET_NAME: str = "youtube-analytics-raw-data-bucket"
    
    # Backend Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["*"]
    
    # Dashboard config
    BACKEND_API_URL: str = "http://localhost:8000/api/v1"
    STREAMLIT_SERVER_PORT: int = 8501

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
