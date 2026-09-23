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
        # Test connection briefly
        with engine.connect() as conn:
            pass
    logger.info(f"Database engine initialized with: {database_url.split('@')[-1] if '@' in database_url else database_url}")
except Exception as e:
    logger.warning(f"Failed to connect to primary database ({e}). Falling back to local SQLite.")
    database_url = "sqlite:///./local_analytics.db"
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False}
    )

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
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")
