import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.router import api_router
from backend.core.database import init_db
from config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("backend")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing YouTube Analytics Platform (Multi-Tenant, Dokploy)...")
    init_db()
    logger.info("Database schema verified and ready.")
    yield
    logger.info("Shutting down backend services.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-user YouTube Analytics Platform with BYOK & Dokploy Docker deployment",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
origins = list(settings.CORS_ORIGINS)
if "https://yap.oxyjet.win" not in origins:
    origins.append("https://yap.oxyjet.win")
if "http://localhost:8501" not in origins:
    origins.append("http://localhost:8501")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router (supporting both /api/v1 and /api)
app.include_router(api_router, prefix="/api/v1")
if settings.API_V1_PREFIX not in ("/api/v1", ""):
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": "2.0.0-multiusers",
        "database": "PostgreSQL / SQLite",
        "domains": {
            "web": f"https://{settings.DOKPLOY_WEB_DOMAIN}",
            "api": f"https://{settings.DOKPLOY_API_DOMAIN}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG
    )
