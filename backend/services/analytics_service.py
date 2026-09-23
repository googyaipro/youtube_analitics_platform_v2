import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.models.channel import Channel
from backend.models.video_metric import VideoMetric

logger = logging.getLogger(__name__)


class AnalyticsService:
    @staticmethod
    def get_set_enriched_videos(
        db: Session,
        user_id: str,
        set_id: str,
        limit: int = 50,
        channel_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Calculate virality factors (channel_avg_views, outlier_score, velocity_vph, engagement_rate_pct)
        using SQL window functions across the user's specific channel set.
        Works seamlessly on both PostgreSQL and SQLite.
        """
        channel_filter = "AND channel_id = :channel_id" if channel_id else ""

        # Cross-dialect ANSI SQL query for PostgreSQL & SQLite (3.25+)
        sql = f"""
            WITH ranked_videos AS (
                SELECT 
                    id, user_id, set_id, video_id, channel_id, channel_title,
                    title, description, view_count, like_count, comment_count,
                    duration, thumbnail_url, published_at, extracted_at,
                    ROUND(AVG(view_count) OVER(PARTITION BY channel_id), 0) AS channel_avg_views,
                    ROW_NUMBER() OVER(PARTITION BY video_id ORDER BY extracted_at DESC) as rn
                FROM video_metrics
                WHERE user_id = :user_id AND set_id = :set_id {channel_filter}
            )
            SELECT * FROM ranked_videos
            WHERE rn = 1
            ORDER BY view_count DESC
            LIMIT :limit;
        """

        params = {"user_id": user_id, "set_id": set_id, "limit": limit}
        if channel_id:
            params["channel_id"] = channel_id

        try:
            results = db.execute(text(sql), params).mappings().all()
            now = datetime.now(timezone.utc)
            enriched = []

            for row in results:
                d = dict(row)
                views = int(d.get("view_count") or 0)
                avg_views = float(d.get("channel_avg_views") or views or 1.0)
                likes = int(d.get("like_count") or 0)
                comments = int(d.get("comment_count") or 0)

                pub_at = d.get("published_at")
                if isinstance(pub_at, str):
                    try:
                        pub_at = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                    except Exception:
                        pub_at = now

                if not isinstance(pub_at, datetime):
                    pub_at = now

                if pub_at.tzinfo is None:
                    pub_at = pub_at.replace(tzinfo=timezone.utc)

                # 1. Outlier multiplier (Hype score relative to channel average)
                outlier = round(views / max(1.0, avg_views), 2)
                d["outlier_score"] = outlier

                # 2. Velocity (Views Per Hour since publish)
                hours_alive = max(1.0, (now - pub_at).total_seconds() / 3600.0)
                vph = round(views / hours_alive, 1)
                d["velocity_vph"] = vph

                # 3. Engagement Rate %
                er = round((likes + comments) / max(1.0, float(views)) * 100.0, 2)
                d["engagement_rate_pct"] = er

                # 4. Generate performance badges
                badges = []
                if outlier >= 2.0:
                    badges.append(f"🚀 Хит {outlier}x")
                elif outlier >= 1.5:
                    badges.append(f"📈 Выше нормы ({outlier}x)")
                if vph >= 100:
                    badges.append(f"⚡ {int(vph)} просм/ч")
                if er >= 2.5:
                    badges.append(f"💬 ER {er:.1f}%")
                d["badges"] = badges

                enriched.append(d)

            return enriched
        except Exception as e:
            logger.error(f"Error executing analytics SQL: {e}")
            return []

    @staticmethod
    def get_set_kpis(db: Session, user_id: str, set_id: str) -> Dict[str, Any]:
        """Compute high-level summary KPIs for a specific channel set."""
        videos = AnalyticsService.get_set_enriched_videos(db, user_id, set_id, limit=200)
        channels_count = db.query(Channel).filter(Channel.user_id == user_id, Channel.set_id == set_id).count()

        if not videos:
            return {
                "total_channels": channels_count,
                "total_videos": 0,
                "total_views": 0,
                "avg_views_per_video": 0,
                "viral_hits_count": 0,
                "top_video": None
            }

        total_views = sum(v.get("view_count", 0) for v in videos)
        hits = [v for v in videos if v.get("outlier_score", 1.0) >= 1.8]
        top_v = videos[0] if videos else None

        return {
            "total_channels": channels_count,
            "total_videos": len(videos),
            "total_views": total_views,
            "avg_views_per_video": int(total_views / max(1, len(videos))),
            "viral_hits_count": len(hits),
            "top_video": {
                "title": top_v.get("title"),
                "channel_title": top_v.get("channel_title"),
                "view_count": top_v.get("view_count"),
                "outlier_score": top_v.get("outlier_score")
            } if top_v else None
        }
