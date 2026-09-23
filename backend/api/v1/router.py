from fastapi import APIRouter
from backend.api.v1.endpoints import (
    auth,
    user,
    channel_sets,
    channels,
    videos,
    analyze,
    cron,
    telegram,
)

api_router = APIRouter()

# Multi-tenant Auth & User settings
api_router.include_router(auth.router)
api_router.include_router(user.router)

# Workspaces / Channel Sets
api_router.include_router(channel_sets.router)

# Data Resources & Analytics
api_router.include_router(channels.router)
api_router.include_router(videos.router)
api_router.include_router(analyze.router)

# Automation & Integrations
api_router.include_router(cron.router)
api_router.include_router(telegram.router)
