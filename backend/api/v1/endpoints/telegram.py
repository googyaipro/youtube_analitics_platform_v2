import logging
from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
import httpx
from sqlalchemy.orm import Session

from backend.core.database import SessionLocal, get_db
from backend.services.telegram_service import TelegramService
from config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])
settings = get_settings()


def _process_telegram_update_task(update_payload: Dict[str, Any]):
    """Background task executing DB transaction and Telegram response safely."""
    db: Session = SessionLocal()
    try:
        TelegramService.handle_webhook_update(db=db, update=update_payload)
    except Exception as e:
        logger.error(f"Error processing Telegram update in background: {e}", exc_info=True)
    finally:
        db.close()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    """
    1. Validates webhook secret header if configured.
    2. Dispatches update processing to FastAPI BackgroundTasks.
    3. Responds 200 OK immediately (< 20ms) to Telegram servers.
    """
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
    if expected_secret and x_telegram_bot_api_secret_token:
        if x_telegram_bot_api_secret_token != expected_secret:
            logger.warning("Unauthorized webhook request: Invalid secret token.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    try:
        update_payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    background_tasks.add_task(_process_telegram_update_task, update_payload)
    return {"ok": True}


@router.post("/setup-webhook")
def setup_webhook():
    """Register Dokploy webhook URL with Telegram Bot API."""
    bot_token = settings.TELEGRAM_BOT_TOKEN
    if not bot_token or " " in bot_token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is not configured")

    webhook_url = f"https://{settings.DOKPLOY_API_DOMAIN}/api/v1/telegram/webhook"
    tg_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    params = {"url": webhook_url}
    if settings.TELEGRAM_WEBHOOK_SECRET:
        params["secret_token"] = settings.TELEGRAM_WEBHOOK_SECRET

    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.post(tg_url, json=params)
            return res.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register webhook with Telegram: {e}")
