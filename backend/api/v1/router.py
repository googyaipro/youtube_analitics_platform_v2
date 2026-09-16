from fastapi import APIRouter
from backend.api.v1.endpoints import (
    analyze,
    channels,
    competitors,
    cron,
    ingestion,
    tasks,
    telegram,
    videos,
)

api_router = APIRouter()

# Webhook & Tasks
api_router.include_router(telegram.router)
api_router.include_router(tasks.router)

# Analytics & AI
api_router.include_router(analyze.router)
api_router.include_router(competitors.router)
api_router.include_router(cron.router)

# Data Resources
api_router.include_router(channels.router)
api_router.include_router(videos.router)
api_router.include_router(ingestion.router)
