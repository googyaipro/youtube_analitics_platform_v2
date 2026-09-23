import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from backend.core.security import decrypt_secret
from backend.models.channel_set import ChannelSet
from backend.models.channel import Channel
from backend.models.video_metric import VideoMetric
from backend.models.user import User
from backend.services.analytics_service import AnalyticsService
from backend.services.gemini_service import GeminiService
from backend.services.youtube_service import YouTubeService
from backend.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)

DAY_NAMES_MAP = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun"
}


class SchedulerService:
    @staticmethod
    def sync_channel_set_data(db: Session, user: User, channel_set: ChannelSet) -> int:
        """Fetch fresh YouTube metrics for all channels in a set using user's personal key."""
        yt_key = decrypt_secret(user.youtube_api_key_encrypted)
        if not yt_key:
            logger.warning(f"User {user.id} has no YouTube API key configured. Skipping sync.")
            return 0

        channels = db.query(Channel).filter(Channel.user_id == user.id, Channel.set_id == channel_set.id).all()
        if not channels:
            return 0

        snapshots_saved = 0
        now = datetime.now(timezone.utc)

        for ch in channels:
            # 1. Update channel statistics
            info = YouTubeService.get_channel_info(ch.channel_id, yt_key)
            if info:
                ch.subscriber_count = info.get("subscriber_count", ch.subscriber_count)
                ch.view_count = info.get("view_count", ch.view_count)
                ch.video_count = info.get("video_count", ch.video_count)
                ch.updated_at = now

            # 2. Grab latest uploads
            recent_vids = YouTubeService.get_channel_recent_videos(ch.channel_id, yt_key, max_results=5)
            for v in recent_vids:
                # Upsert or insert new snapshot
                existing = db.query(VideoMetric).filter(
                    VideoMetric.user_id == user.id,
                    VideoMetric.set_id == channel_set.id,
                    VideoMetric.video_id == v["video_id"]
                ).first()

                if existing:
                    existing.view_count = v["view_count"]
                    existing.like_count = v["like_count"]
                    existing.comment_count = v["comment_count"]
                    existing.extracted_at = now
                else:
                    db.add(VideoMetric(
                        user_id=user.id,
                        set_id=channel_set.id,
                        video_id=v["video_id"],
                        channel_id=ch.channel_id,
                        channel_title=v["channel_title"],
                        title=v["title"],
                        description=v["description"],
                        view_count=v["view_count"],
                        like_count=v["like_count"],
                        comment_count=v["comment_count"],
                        duration=v.get("duration"),
                        thumbnail_url=v.get("thumbnail_url"),
                        published_at=v["published_at"],
                        extracted_at=now
                    ))
                snapshots_saved += 1

        db.commit()
        return snapshots_saved

    @classmethod
    def dispatch_scheduled_sets(cls, db: Session) -> Dict[str, Any]:
        """
        Hourly dispatcher:
        Scans all active channel sets and triggers data sync + AI digest
        for sets matching the current hour in their configured timezone.
        """
        utc_now = datetime.now(timezone.utc)
        active_sets = db.query(ChannelSet).filter(ChannelSet.schedule_enabled == True).all()

        dispatched_count = 0
        notified_users_count = 0
        details: List[str] = []

        for c_set in active_sets:
            user = db.query(User).filter(User.id == c_set.user_id).first()
            if not user or not user.is_active:
                continue

            # Convert UTC now to set's local timezone
            try:
                tz = ZoneInfo(c_set.schedule_timezone or "Europe/Helsinki")
                local_now = utc_now.astimezone(tz)
            except Exception as e:
                logger.warning(f"Invalid timezone {c_set.schedule_timezone} on set {c_set.id}: {e}")
                tz = ZoneInfo("Europe/Helsinki")
                local_now = utc_now.astimezone(tz)

            # Check day of week
            current_day_code = DAY_NAMES_MAP[local_now.weekday()]
            allowed_days = [d.strip().lower() for d in (c_set.schedule_days or "").split(",")]
            if current_day_code not in allowed_days:
                continue

            # Check time (HH:MM matching current local hour)
            target_time = c_set.schedule_time or "12:00"
            try:
                target_hour = int(target_time.split(":")[0])
            except Exception:
                target_hour = 12

            if local_now.hour != target_hour:
                continue

            # Avoid executing multiple times in the same hour
            if c_set.last_run_at:
                last_run_local = c_set.last_run_at.astimezone(tz) if c_set.last_run_at.tzinfo else c_set.last_run_at.replace(tzinfo=timezone.utc).astimezone(tz)
                if last_run_local.date() == local_now.date() and last_run_local.hour == local_now.hour:
                    continue

            logger.info(f"Triggering scheduled digest for set '{c_set.name}' (User: {user.email}) at {local_now.strftime('%Y-%m-%d %H:%M %Z')}")

            # 1. Sync fresh data via YouTube API (BYOK)
            snapshots_count = cls.sync_channel_set_data(db, user, c_set)

            # 2. Get top videos and factor analysis
            enriched_videos = AnalyticsService.get_set_enriched_videos(db, user.id, c_set.id, limit=10)
            channels = db.query(Channel).filter(Channel.user_id == user.id, Channel.set_id == c_set.id).all()
            channels_summary = [{"title": c.title, "subscriber_count": c.subscriber_count} for c in channels]

            anomalies = []
            for v in enriched_videos:
                if v.get("outlier_score", 1.0) >= 1.8:
                    anomalies.append(f"Канал {v.get('channel_title')}: «{v.get('title')}» — {v.get('view_count'):,} просмотров ({v.get('outlier_score')}x)")

            # 3. Generate Gemini digest using user's key and language
            gemini_key = decrypt_secret(user.gemini_api_key_encrypted)
            lang = user.language or "ru"
            digest_text = GeminiService.generate_daily_digest(
                set_name=c_set.name,
                channels_summary=channels_summary,
                top_videos=enriched_videos,
                anomalies=anomalies,
                target_language=lang,
                gemini_api_key=gemini_key
            )

            # 4. Deliver to Telegram if user connected their chat
            if user.telegram_chat_id:
                sent = TelegramService.send_message(user.telegram_chat_id, digest_text)
                if sent:
                    notified_users_count += 1

            c_set.last_run_at = utc_now
            db.commit()

            dispatched_count += 1
            details.append(f"Set '{c_set.name}' (User {user.email}): {snapshots_count} videos synced.")

        return {
            "status": "SUCCESS",
            "current_utc": utc_now.isoformat(),
            "dispatched_sets_count": dispatched_count,
            "notified_users_count": notified_users_count,
            "details": details
        }
