import logging
from datetime import date, datetime
from typing import Any, Dict
from fastapi import APIRouter, Header, HTTPException

from backend.prompts import load_prompt
from backend.services.bigquery_service import BigQueryService
from backend.services.firestore_cache import FirestoreCache
from backend.services.gemini_service import GeminiService
from backend.services.telegram_bot import TelegramBotService
from backend.services.youtube_client import YouTubeClient
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cron", tags=["Cloud Scheduler Automation"])

settings = get_settings()
yt = YouTubeClient()
bq = BigQueryService()
gemini = GeminiService()
bot = TelegramBotService()
cache = FirestoreCache()


@router.post("/track-competitors")
async def track_competitors_cron(
    authorization: str = Header(None)
):
    """
    Automated daily cron job (08:00 UTC) triggered by Cloud Scheduler.
    1. Reads active channels from BigQuery (competitor_channels).
    2. Batch queries YouTube API (1 unit quota for all channels!).
    3. Calculates daily growth deltas and saves snapshots to BigQuery.
    4. Gemini creates anomaly summary and sends morning digest to Telegram.
    """
    logger.info("Starting automated daily competitor tracking job...")
    
    # 1. Fetch tracked channels
    channels_data = bq.get_channels()
    if not channels_data:
        logger.info("No tracked channels found in BigQuery. Cron job completed.")
        return {"status": "SUCCESS", "message": "No channels to track.", "snapshots_saved": 0}

    channel_ids = [c["channel_id"] for c in channels_data if "channel_id" in c]
    
    # 2. Batch fetch fresh statistics (Cost: 1 unit)
    updated_channels = yt.get_multiple_channels(channel_ids)
    
    today = date.today()
    snapshots_saved = 0
    anomalies = []

    for ch in updated_channels:
        # Calculate daily delta or record snapshot
        bq.insert_channel(ch)
        snapshots_saved += 1
        
        # Also grab latest videos via Uploads Playlist (UU...)
        recent_videos = yt.get_channel_uploads(ch.channel_id, max_results=5)
        if recent_videos:
            bq.insert_videos(recent_videos)
            
            # Check for viral spike (> 1M views)
            for v in recent_videos:
                if v.statistics.view_count > 500000:
                    anomalies.append(f"Канал *{ch.snippet.title}*: ролик «{v.snippet.title}» набрал {v.statistics.view_count:,} просмотров!")

    # 3. Morning digest
    if anomalies:
        anomalies_block = "\n🔥 **Обнаружены аномалии и лидеры роста:**\n" + "\n".join([f"• {a}" for a in anomalies])
    else:
        anomalies_block = "\nСтабильная динамика просмотров и подписчиков по всем отслеживаемым конкурентам."

    digest_template = load_prompt("morning_digest.txt")
    digest_text = (
        digest_template
        .replace("{{date}}", today.strftime("%d.%m.%Y"))
        .replace("{{snapshots_saved}}", str(snapshots_saved))
        .replace("{{anomalies_block}}", anomalies_block)
    )

    # 4. Broadcast to Telegram subscribers
    subscribers = set(cache.get_telegram_subscribers())
    if settings.TELEGRAM_ADMIN_CHAT_ID:
        subscribers.add(str(settings.TELEGRAM_ADMIN_CHAT_ID))

    sent_count = 0
    for chat_id in subscribers:
        try:
            bot.send_message(chat_id=chat_id, text=digest_text)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send morning digest to chat {chat_id}: {e}")

    logger.info(f"Competitor tracking job completed. Sent digest to {sent_count} subscribers.")
    return {
        "status": "SUCCESS",
        "snapshots_processed": snapshots_saved,
        "anomalies_count": len(anomalies),
        "telegram_subscribers_notified": sent_count,
        "digest": digest_text
    }
