import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services.scheduler_service import SchedulerService
from config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cron", tags=["Scheduler Automation"])
settings = get_settings()


@router.post("/dispatch-schedules", response_model=Dict[str, Any])
@router.get("/dispatch-schedules", response_model=Dict[str, Any])
def dispatch_hourly_schedules(
    x_cron_secret: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Automated dispatcher triggered hourly by Dokploy cron or server scheduler.
    Scans all user channel sets, checks local timezone and configured schedule,
    fetches YouTube metrics with user keys, generates multilingual Gemini digests,
    and sends them to connected Telegram chats.
    """
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
    # If a secret is configured in env, require it when triggered externally
    if expected_secret and x_cron_secret:
        if x_cron_secret != expected_secret:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid cron secret")

    logger.info("Starting hourly channel sets dispatcher...")
    result = SchedulerService.dispatch_scheduled_sets(db=db)
    logger.info(f"Dispatcher completed: {result['dispatched_sets_count']} sets processed, {result['notified_users_count']} users notified.")
    return result


@router.post("/track-competitors", response_model=Dict[str, Any])
def legacy_track_competitors(db: Session = Depends(get_db)):
    """Legacy alias for dispatching schedules."""
    return SchedulerService.dispatch_scheduled_sets(db=db)
