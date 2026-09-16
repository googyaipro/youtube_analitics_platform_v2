from fastapi import APIRouter
from backend.api.v1.endpoints import channels, videos, ingestion

api_router = APIRouter()
api_router.include_router(channels.router)
api_router.include_router(videos.router)
api_router.include_router(ingestion.router)
