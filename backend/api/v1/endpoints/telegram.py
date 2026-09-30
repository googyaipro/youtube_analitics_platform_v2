import logging
from typing import Any, Dict, Optional
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
    x_telegram_bot_api_secret_token: Optional[str] = Header(None)
):
    """
    1. Validates webhook secret header if configured.
    2. Dispatches update processing to FastAPI BackgroundTasks.
    3. Responds 200 OK immediately (< 20ms) to Telegram servers.
    """
    expected_secret = (settings.TELEGRAM_WEBHOOK_SECRET or "").strip().strip('"').strip("'")
    if expected_secret:
        raw_header = (
            x_telegram_bot_api_secret_token
            or request.headers.get("x-telegram-bot-api-secret-token")
            or request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            or ""
        )
        token = raw_header.strip().strip('"').strip("'")
        if not token or token != expected_secret:
            logger.warning(
                f"Unauthorized webhook request: secret token mismatch "
                f"(received_len={len(token)}, expected_len={len(expected_secret)})"
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    try:
        update_payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    background_tasks.add_task(_process_telegram_update_task, update_payload)
    return {"ok": True}


@router.post("/setup-webhook")
def setup_webhook(x_admin_secret: Optional[str] = Header(None)):
    """Register Dokploy webhook URL with Telegram Bot API."""
    expected_admin = (settings.ADMIN_SECRET or settings.CRON_SECRET or settings.TELEGRAM_WEBHOOK_SECRET or "").strip().strip('"').strip("'")
    incoming_admin = (x_admin_secret or "").strip().strip('"').strip("'")
    if expected_admin and incoming_admin != expected_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Admin secret required")

    return TelegramService.register_webhook()

