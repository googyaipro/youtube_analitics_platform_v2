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

# Prepare engine configuration
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
    """Create all tables in the database with connection retries."""
    global engine, SessionLocal
    import time
    
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables initialized successfully.")
            return
        except Exception as e:
            err_str = str(e)
            logger.warning(f"Database connection attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries and "could not translate host name" not in err_str and "Name or service not known" not in err_str:
                time.sleep(1)
            else:
                logger.info("Falling back to local SQLite database.")
                sqlite_url = "sqlite:///./local_analytics.db"
                engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
                SessionLocal.configure(bind=engine)
                Base.metadata.create_all(bind=engine)
                logger.info("Fallback SQLite database initialized successfully.")
                return

