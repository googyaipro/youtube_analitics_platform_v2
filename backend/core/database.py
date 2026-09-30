import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

database_url = settings.DATABASE_URL

# Handle Heroku/Dokploy postgres:// to postgresql:// if needed
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

import os
import time

# Ensure persistent directory exists for SQLite fallback
DATA_DIR = "/app/data" if os.path.exists("/app") else "./data"
os.makedirs(DATA_DIR, exist_ok=True)
PERSISTENT_SQLITE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'local_analytics.db')}"

try:
    if "sqlite" in database_url:
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False}
        )
    else:
        # PostgreSQL engine with pool_pre_ping for resilient connections
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
    logger.info(f"Database engine configured for: {database_url.split('@')[-1] if '@' in database_url else database_url}")
except Exception as e:
    logger.warning(f"Could not initialize primary database engine: {e}. Falling back to persistent SQLite.")
    database_url = PERSISTENT_SQLITE_URL
    engine = create_engine(database_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables in the database with resilient connection retries."""
    global engine, SessionLocal

    # Ensure all model tables are registered in Base.metadata
    try:
        from backend.models.user import User  # noqa: F401
        from backend.models.channel_set import ChannelSet  # noqa: F401
        from backend.models.channel import Channel  # noqa: F401
        from backend.models.video_metric import VideoMetric  # noqa: F401
    except Exception as e:
        logger.warning(f"Model import error during init_db: {e}")
    
    max_retries = 15
    for attempt in range(1, max_retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables initialized successfully on primary engine.")
            return
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(2)
            else:
                logger.error("Could not connect to PostgreSQL after retries. Falling back to persistent SQLite volume.")
                engine = create_engine(PERSISTENT_SQLITE_URL, connect_args={"check_same_thread": False})
                SessionLocal.configure(bind=engine)
                Base.metadata.create_all(bind=engine)
                logger.info(f"Fallback persistent SQLite database initialized at {PERSISTENT_SQLITE_URL}")
                return

