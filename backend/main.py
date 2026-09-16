import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.router import api_router
from backend.services.bigquery_service import BigQueryService
from backend.services.youtube_client import YouTubeClient
from config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("backend")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing YouTube Analytics Platform backend...")
    bq = BigQueryService()
    bq.init_dataset_and_tables()
    
    yield
    logger.info("Shutting down backend services.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Full-stack YouTube Analytics Platform with Google Cloud BigQuery & Storage integration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "gcp_project": settings.GCP_PROJECT_ID,
        "bigquery_dataset": settings.BIGQUERY_DATASET_ID
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG
    )
