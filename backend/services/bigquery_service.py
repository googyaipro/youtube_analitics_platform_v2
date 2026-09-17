import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from backend.models.channel import Channel
from backend.models.video import Video
from config.settings import get_settings

logger = logging.getLogger(__name__)


class BigQueryService:
    def __init__(self):
        settings = get_settings()
        self.project_id = settings.GCP_PROJECT_ID
        self.dataset_id = settings.BIGQUERY_DATASET_ID
        self.location = settings.GCP_LOCATION
        self._client: Optional[bigquery.Client] = None
        
        # In-memory storage fallback for local development without active GCP credentials
        self._mock_channels: Dict[str, Dict[str, Any]] = {}
        self._mock_videos: Dict[str, Dict[str, Any]] = {}

        try:
            self._client = bigquery.Client(project=self.project_id, location=self.location)
            logger.info("Google Cloud BigQuery client initialized.")
        except Exception as e:
            logger.warning(f"BigQuery client initialization failed (using local in-memory fallback): {e}")

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def init_dataset_and_tables(self) -> bool:
        """Create BigQuery dataset and analytical tables if they don't exist."""
        if not self.is_connected:
            logger.info("BigQuery not connected. Tables initialized in memory.")
            return True

        try:
            dataset_ref = f"{self.project_id}.{self.dataset_id}"
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = self.location
            self._client.create_dataset(dataset, exists_ok=True)
            logger.info(f"Dataset {dataset_ref} verified/created.")

            # 1. Channels Table Schema
            channels_table_ref = f"{dataset_ref}.channels"
            channels_schema = [
                bigquery.SchemaField("channel_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("title", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("custom_url", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("subscriber_count", "INT64", mode="NULLABLE"),
                bigquery.SchemaField("view_count", "INT64", mode="NULLABLE"),
                bigquery.SchemaField("video_count", "INT64", mode="NULLABLE"),
                bigquery.SchemaField("country", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("published_at", "TIMESTAMP", mode="NULLABLE"),
                bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
            ]
            channels_table = bigquery.Table(channels_table_ref, schema=channels_schema)
            self._client.create_table(channels_table, exists_ok=True)

            # 2. Video Metrics Table Schema
            videos_table_ref = f"{dataset_ref}.video_metrics"
            videos_schema = [
                bigquery.SchemaField("video_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("channel_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("channel_title", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("title", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("published_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("view_count", "INT64", mode="REQUIRED"),
                bigquery.SchemaField("like_count", "INT64", mode="NULLABLE"),
                bigquery.SchemaField("comment_count", "INT64", mode="NULLABLE"),
                bigquery.SchemaField("duration", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("thumbnail_url", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="REQUIRED"),
            ]
            videos_table = bigquery.Table(videos_table_ref, schema=videos_schema)
            self._client.create_table(videos_table, exists_ok=True)
            logger.info("BigQuery tables verified/created successfully.")
            return True
        except Exception as e:
            logger.error(f"Error initializing BigQuery resources: {e}")
            return False

    def insert_channel(self, channel: Channel) -> bool:
        row = {
            "channel_id": channel.channel_id,
            "title": channel.snippet.title,
            "custom_url": channel.snippet.custom_url,
            "description": channel.snippet.description,
            "subscriber_count": channel.statistics.subscriber_count,
            "view_count": channel.statistics.view_count,
            "video_count": channel.statistics.video_count,
            "country": channel.snippet.country,
            "published_at": channel.snippet.published_at.isoformat() if channel.snippet.published_at else None,
            "updated_at": channel.extracted_at.isoformat(),
        }
        self._mock_channels[channel.channel_id] = row

        if not self.is_connected:
            return True

        try:
            table_ref = f"{self.project_id}.{self.dataset_id}.channels"
            errors = self._client.insert_rows_json(table_ref, [row])
            if errors:
                logger.error(f"Errors inserting channel to BigQuery: {errors}")
                return False
            return True
        except Exception as e:
            logger.error(f"Exception inserting channel to BigQuery: {e}")
            return False

    def insert_videos(self, videos: List[Video]) -> bool:
        rows = []
        for v in videos:
            row = {
                "video_id": v.video_id,
                "channel_id": v.snippet.channel_id,
                "channel_title": v.snippet.channel_title,
                "title": v.snippet.title,
                "description": v.snippet.description,
                "published_at": v.snippet.published_at.isoformat(),
                "view_count": v.statistics.view_count,
                "like_count": v.statistics.like_count,
                "comment_count": v.statistics.comment_count,
                "duration": v.duration,
                "thumbnail_url": v.snippet.thumbnail_url,
                "extracted_at": v.extracted_at.isoformat(),
            }
            rows.append(row)
            self._mock_videos[v.video_id] = row

        if not self.is_connected:
            return True

        try:
            table_ref = f"{self.project_id}.{self.dataset_id}.video_metrics"
            errors = self._client.insert_rows_json(table_ref, rows)
            if errors:
                logger.error(f"Errors inserting videos into BigQuery: {errors}")
                return False
            return True
        except Exception as e:
            logger.error(f"Exception inserting videos into BigQuery: {e}")
            return False

    def get_channels(self) -> List[Dict[str, Any]]:
        if not self.is_connected:
            return list(self._mock_channels.values())

        try:
            query = f"""
                SELECT channel_id, title, custom_url, subscriber_count, view_count, video_count, country, published_at, updated_at
                FROM `{self.project_id}.{self.dataset_id}.channels`
                WHERE channel_id NOT IN (SELECT channel_id FROM `{self.project_id}.{self.dataset_id}.excluded_channels`)
                ORDER BY updated_at DESC
            """
            job = self._client.query(query)
            seen = set()
            unique_channels = []
            for row in job.result():
                d = dict(row)
                cid = d.get("channel_id")
                if cid and cid not in seen:
                    seen.add(cid)
                    unique_channels.append(d)
            return unique_channels
        except Exception as e:
            logger.warning(f"Error querying BigQuery channels ({e}), falling back to cache.")
            return list(self._mock_channels.values())

    def delete_channel(self, channel_id: str) -> bool:
        """
        Delete channel using Tombstone pattern (bypasses BigQuery streaming buffer 400 error).
        Immediately excludes channel from all queries and views via `excluded_channels`.
        """
        if channel_id in self._mock_channels:
            del self._mock_channels[channel_id]

        if not self.is_connected:
            return True

        try:
            # 1. Insert into excluded_channels (Tombstone - never blocked by streaming buffer)
            tombstone = {
                "channel_id": channel_id,
                "deleted_at": datetime.utcnow().isoformat()
            }
            table_ref = f"{self.project_id}.{self.dataset_id}.excluded_channels"
            errors = self._client.insert_rows_json(table_ref, [tombstone])
            if errors:
                logger.warning(f"Error inserting tombstone: {errors}")

            # 2. Best-effort hard delete (succeeds if rows are flushed from buffer)
            try:
                for table_name in ["competitor_channels", "channels"]:
                    query = f"DELETE FROM `{self.project_id}.{self.dataset_id}.{table_name}` WHERE channel_id = '{channel_id}'"
                    self._client.query(query).result()
            except Exception as dml_err:
                logger.info(f"DML delete deferred until streaming buffer flush: {dml_err}")

            logger.info(f"Successfully excluded/deleted channel {channel_id}.")
            return True
        except Exception as e:
            logger.error(f"Error in delete_channel for {channel_id}: {e}")
            return False

    def get_videos(self, channel_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.is_connected:
            vids = list(self._mock_videos.values())
            if channel_id:
                vids = [v for v in vids if v.get("channel_id") == channel_id]
            vids.sort(key=lambda x: x.get("view_count", 0), reverse=True)
            return vids[:limit]

        try:
            conditions = [
                f"channel_id NOT IN (SELECT channel_id FROM `{self.project_id}.{self.dataset_id}.excluded_channels`)"
            ]
            if channel_id:
                conditions.append(f"channel_id = '{channel_id}'")
            where_clause = "WHERE " + " AND ".join(conditions)

            query = f"""
                WITH enriched AS (
                    SELECT video_id, channel_id, channel_title, title, description, published_at,
                           view_count, like_count, comment_count, duration, thumbnail_url, extracted_at,
                           ROUND(AVG(view_count) OVER(PARTITION BY channel_id), 0) AS channel_avg_views,
                           ROUND(view_count / NULLIF(AVG(view_count) OVER(PARTITION BY channel_id), 0), 2) AS outlier_score,
                           ROUND(view_count / GREATEST(1, TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), published_at, HOUR)), 1) AS velocity_vph,
                           ROUND((like_count + comment_count) / NULLIF(view_count, 0) * 100, 2) AS engagement_rate_pct
                    FROM `{self.project_id}.{self.dataset_id}.video_metrics`
                    {where_clause}
                )
                SELECT * FROM enriched
                ORDER BY view_count DESC
                LIMIT {limit}
            """
            job = self._client.query(query)
            seen = set()
            unique_videos = []
            for row in job.result():
                d = dict(row)
                vid = d.get("video_id")
                if vid and vid not in seen:
                    seen.add(vid)
                    # Generate human-readable performance badges
                    badges = []
                    score = float(d.get("outlier_score") or 1.0)
                    vph = float(d.get("velocity_vph") or 0.0)
                    er = float(d.get("engagement_rate_pct") or 0.0)
                    if score >= 2.0:
                        badges.append(f"🚀 Хит {score}x")
                    elif score >= 1.5:
                        badges.append(f"📈 Выше нормы ({score}x)")
                    if vph >= 100:
                        badges.append(f"⚡ {int(vph)} просм/ч")
                    if er >= 2.5:
                        badges.append(f"💬 ER {er:.1f}%")
                    d["badges"] = badges
                    unique_videos.append(d)
            return unique_videos
        except Exception as e:
            logger.warning(f"Error querying BigQuery videos ({e}), falling back to cache.")
            vids = list(self._mock_videos.values())
            if channel_id:
                vids = [v for v in vids if v.get("channel_id") == channel_id]
            return vids[:limit]

    def get_video_by_id_or_title(self, query: str) -> Optional[Dict[str, Any]]:
        """Find video by video_id, URL, rank number, or title keywords."""
        clean_q = query.strip()
        videos = self.get_videos(limit=200)
        if not videos:
            return None

        # 1. Check if user specified a rank number (e.g., '1', '#1', 'топ 1')
        clean_digits = re.sub(r"[^\d]", "", clean_q)
        if clean_digits and (clean_q.startswith("#") or clean_q.isdigit() or "топ" in clean_q.lower() or "top" in clean_q.lower()):
            idx = int(clean_digits) - 1
            if 0 <= idx < len(videos):
                return videos[idx]

        # 2. Check if YouTube URL or exact 11-char video ID
        url_match = re.search(r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})", clean_q)
        target_id = url_match.group(1) if url_match else clean_q

        for v in videos:
            if v.get("video_id") == target_id:
                return v

        # 3. Case-insensitive title match
        lowered = clean_q.lower()
        for v in videos:
            if lowered in (v.get("title") or "").lower():
                return v

        # 4. Keyword words match (words > 3 chars)
        keywords = [w for w in lowered.split() if len(w) > 3 and w not in ["почему", "выстрелил", "видео", "ролик", "разбор", "канал"]]
        if keywords:
            for v in videos:
                t = (v.get("title") or "").lower()
                if any(kw in t for kw in keywords):
                    return v

        return videos[0]

    def get_kpis(self) -> Dict[str, Any]:
        videos = self.get_videos(limit=500)
        channels = self.get_channels()

        total_views = sum(v.get("view_count", 0) for v in videos)
        total_likes = sum(v.get("like_count", 0) for v in videos)
        total_comments = sum(v.get("comment_count", 0) for v in videos)
        total_subscribers = sum(c.get("subscriber_count", 0) for c in channels)

        engagement_rate = (
            (total_likes + total_comments) / total_views * 100
            if total_views > 0
            else 0.0
        )

        return {
            "total_channels": len(channels),
            "total_videos": len(videos),
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_subscribers": total_subscribers,
            "engagement_rate_pct": round(engagement_rate, 2),
        }
