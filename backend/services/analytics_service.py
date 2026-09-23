import logging
import re
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.models.channel import Channel
from backend.models.video_metric import VideoMetric

logger = logging.getLogger(__name__)


def parse_iso8601_duration(duration_str: Optional[str]) -> Tuple[int, str]:
    """
    Parse ISO 8601 duration (e.g. PT1H2M30S, PT15M42S, PT45S) into total seconds
    and a human-readable display string (HH:MM:SS or MM:SS).
    """
    if not duration_str:
        return 0, "--:--"

    pattern = r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match = re.match(pattern, duration_str)
    if not match:
        return 0, "--:--"

    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = int(match.group(4) or 0)

    total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds

    if hours > 0 or days > 0:
        total_hours = days * 24 + hours
        formatted = f"{total_hours}:{minutes:02d}:{seconds:02d}"
    else:
        formatted = f"{minutes}:{seconds:02d}"

    return total_seconds, formatted


class AnalyticsService:
    @staticmethod
    def get_set_enriched_videos(
        db: Session,
        user_id: str,
        set_id: str,
        limit: int = 50,
        channel_id: Optional[str] = None,
        format_filter: Optional[str] = "all",
        sort_by: Optional[str] = "views"
    ) -> List[Dict[str, Any]]:
        """
        Calculate virality factors using format-aware median baselines,
        Shorts vs Long-form separation, audience penetration (Views/Subs),
        and multi-criteria ranking.
        """
        channel_filter = "AND channel_id = :channel_id" if channel_id else ""

        # Fetch latest snapshot per video in this set
        sql = f"""
            WITH ranked_snapshots AS (
                SELECT 
                    id, user_id, set_id, video_id, channel_id, channel_title,
                    title, description, view_count, like_count, comment_count,
                    duration, thumbnail_url, published_at, extracted_at,
                    ROW_NUMBER() OVER(PARTITION BY video_id ORDER BY extracted_at DESC) as rn
                FROM video_metrics
                WHERE user_id = :user_id AND set_id = :set_id {channel_filter}
            )
            SELECT * FROM ranked_snapshots WHERE rn = 1;
        """

        params = {"user_id": user_id, "set_id": set_id}
        if channel_id:
            params["channel_id"] = channel_id

        try:
            results = db.execute(text(sql), params).mappings().all()
            if not results:
                return []

            # 1. Fetch channel subscriber counts for subscriber penetration ratio
            channels_query = db.query(Channel.channel_id, Channel.subscriber_count).filter(
                Channel.user_id == user_id,
                Channel.set_id == set_id
            ).all()
            channel_subs_map = {c[0]: (c[1] or 0) for c in channels_query}

            now = datetime.now(timezone.utc)
            parsed_rows = []

            # Groupings for format-specific median calculations
            channel_views_long: Dict[str, List[int]] = {}
            channel_views_short: Dict[str, List[int]] = {}
            channel_views_all: Dict[str, List[int]] = {}

            # First pass: parse durations, formats, and collect distributions
            for row in results:
                d = dict(row)
                views = int(d.get("view_count") or 0)
                d["view_count"] = views
                likes = int(d.get("like_count") or 0)
                d["like_count"] = likes
                comments = int(d.get("comment_count") or 0)
                d["comment_count"] = comments

                # Parse duration and format
                duration_raw = d.get("duration")
                dur_secs, dur_formatted = parse_iso8601_duration(duration_raw)
                d["duration_seconds"] = dur_secs
                d["duration_formatted"] = dur_formatted
                is_short = 0 < dur_secs <= 60
                d["is_short"] = is_short
                d["format_type"] = "short" if is_short else "long"

                # Parse published_at
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
                d["published_at_dt"] = pub_at
                d["published_at"] = pub_at.isoformat()

                # Collect views per channel & format
                ch_id = d.get("channel_id", "")
                channel_views_all.setdefault(ch_id, []).append(views)
                if is_short:
                    channel_views_short.setdefault(ch_id, []).append(views)
                else:
                    channel_views_long.setdefault(ch_id, []).append(views)

                parsed_rows.append(d)

            # Precalculate medians per channel
            def get_median(lst: List[int]) -> float:
                if not lst:
                    return 1.0
                return float(statistics.median(lst))

            channel_median_all = {cid: get_median(v) for cid, v in channel_views_all.items()}
            channel_median_long = {
                cid: get_median(v) if len(v) >= 2 else channel_median_all.get(cid, 1.0)
                for cid, v in channel_views_long.items()
            }
            channel_median_short = {
                cid: get_median(v) if len(v) >= 2 else channel_median_all.get(cid, 1.0)
                for cid, v in channel_views_short.items()
            }

            # Second pass: calculate enriched metrics
            enriched = []
            for d in parsed_rows:
                ch_id = d.get("channel_id", "")
                views = d["view_count"]
                is_short = d["is_short"]
                pub_at = d["published_at_dt"]

                # 1. Format-aware median baseline
                if is_short:
                    baseline_views = channel_median_short.get(ch_id, channel_median_all.get(ch_id, views or 1.0))
                else:
                    baseline_views = channel_median_long.get(ch_id, channel_median_all.get(ch_id, views or 1.0))
                baseline_views = max(1.0, float(baseline_views))
                d["channel_avg_views"] = int(baseline_views)
                d["channel_median_views"] = int(baseline_views)

                # 2. Outlier multiplier (Hype score relative to format median)
                outlier = round(views / baseline_views, 2)
                d["outlier_score"] = outlier

                # 3. Velocity (Views Per Hour)
                hours_alive = max(1.0, (now - pub_at).total_seconds() / 3600.0)
                vph = round(views / hours_alive, 1)
                d["velocity_vph"] = vph

                # 4. Engagement Rate %
                er = round((d["like_count"] + d["comment_count"]) / max(1.0, float(views)) * 100.0, 2)
                d["engagement_rate_pct"] = er

                # 5. Audience penetration (Views to Subscribers Ratio)
                subs = channel_subs_map.get(ch_id, 0)
                d["subscriber_count"] = subs
                views_to_subs = round((views / max(1, subs)) * 100.0, 1) if subs > 0 else 0.0
                d["views_to_subs_pct"] = views_to_subs

                # 6. Performance badges
                badges = []
                badges.append("📱 Shorts" if is_short else "🎬 Video")
                if outlier >= 2.0:
                    badges.append(f"🚀 Хит {outlier}x")
                elif outlier >= 1.5:
                    badges.append(f"📈 Выше нормы ({outlier}x)")
                if vph >= 100:
                    badges.append(f"⚡ {int(vph)} просм/ч")
                if er >= 2.5:
                    badges.append(f"💬 ER {er:.1f}%")
                if views_to_subs >= 100.0:
                    badges.append(f"💎 {int(views_to_subs)}% к подп.")

                d["badges"] = badges
                enriched.append(d)

            # 7. Apply format filter
            if format_filter == "long":
                enriched = [v for v in enriched if not v["is_short"]]
            elif format_filter == "short":
                enriched = [v for v in enriched if v["is_short"]]

            # 8. Multi-criteria sorting
            if sort_by == "outlier":
                enriched.sort(key=lambda x: (x.get("outlier_score", 0.0), x.get("view_count", 0)), reverse=True)
            elif sort_by == "vph":
                enriched.sort(key=lambda x: (x.get("velocity_vph", 0.0), x.get("view_count", 0)), reverse=True)
            elif sort_by == "published_at":
                enriched.sort(key=lambda x: x.get("published_at_dt", now), reverse=True)
            elif sort_by == "views_to_subs":
                enriched.sort(key=lambda x: (x.get("views_to_subs_pct", 0.0), x.get("view_count", 0)), reverse=True)
            else:  # default "views"
                enriched.sort(key=lambda x: x.get("view_count", 0), reverse=True)

            # Cleanup helper datetime before serialization
            for v in enriched:
                v.pop("published_at_dt", None)

            return enriched[:limit]

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

