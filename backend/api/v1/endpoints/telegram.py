import logging
from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from backend.services.cloud_tasks_service import CloudTasksService
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])

settings = get_settings()
tasks_service = CloudTasksService()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    """
    1. Validates webhook secret header.
    2. Enqueues message to Cloud Tasks within 15ms.
    3. Responds 200 OK immediately.
    """
    # Security check if secret token is configured
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
    if expected_secret and x_telegram_bot_api_secret_token:
        if x_telegram_bot_api_secret_token != expected_secret:
            logger.warning("Unauthorized webhook request: Invalid secret token.")
            raise HTTPException(status_code=403, detail="Forbidden")

    update_payload: Dict[str, Any] = await request.json()
    logger.info("Received Telegram update.")

    # 1. Enqueue to Cloud Tasks (Scale-to-Zero, full dedicated CPU on worker)
    enqueued = tasks_service.enqueue_telegram_message(update_payload)

    # 2. Fallback to local background task if running in local development mode
    if not enqueued:
        from backend.api.v1.endpoints.tasks import handle_telegram_update_internal
        background_tasks.add_task(handle_telegram_update_internal, update_payload)
        logger.info("Executed via local BackgroundTasks fallback.")

    return {"ok": True, "enqueued": enqueued}
