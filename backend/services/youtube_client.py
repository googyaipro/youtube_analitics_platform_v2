import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.models.channel import Channel, ChannelSnippet, ChannelStatistics
from backend.models.video import Video, VideoSnippet, VideoStatistics
from config.settings import get_settings

logger = logging.getLogger(__name__)


class YouTubeClient:
    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.YOUTUBE_API_KEY
        self._service = None
        if self.api_key:
            try:
                self._service = build("youtube", "v3", developerKey=self.api_key)
                logger.info("YouTube Data API client initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize YouTube API client: {e}")

    @property
    def is_configured(self) -> bool:
        return self._service is not None

    def get_channel(self, channel_identifier: str) -> Optional[Channel]:
        """Fetch channel metadata by channel ID or handle (e.g., @GoogleCloud)."""
        if not self.is_configured:
            logger.info("No YouTube API Key provided. Returning sample channel data.")
            return self._generate_mock_channel(channel_identifier)

        try:
            request = None
            if channel_identifier.startswith("@"):
                request = self._service.channels().list(
                    part="snippet,contentDetails,statistics",
                    forHandle=channel_identifier
                )
            elif channel_identifier.startswith("UC"):
                request = self._service.channels().list(
                    part="snippet,contentDetails,statistics",
                    id=channel_identifier
                )
            else:
                # Try search or username
                request = self._service.channels().list(
                    part="snippet,contentDetails,statistics",
                    forUsername=channel_identifier
                )

            response = request.execute()
            items = response.get("items", [])
            if not items:
                logger.warning(f"Channel not found: {channel_identifier}")
                return None

            item = items[0]
            snippet_data = item.get("snippet", {})
            stats_data = item.get("statistics", {})

            return Channel(
                channel_id=item["id"],
                snippet=ChannelSnippet(
                    title=snippet_data.get("title", ""),
                    description=snippet_data.get("description", ""),
                    custom_url=snippet_data.get("customUrl"),
                    published_at=datetime.fromisoformat(snippet_data["publishedAt"].replace("Z", "+00:00")),
                    thumbnail_url=snippet_data.get("thumbnails", {}).get("high", {}).get("url"),
                    country=snippet_data.get("country")
                ),
                statistics=ChannelStatistics(
                    view_count=int(stats_data.get("viewCount", 0)),
                    subscriber_count=int(stats_data.get("subscriberCount", 0)),
                    hidden_subscriber_count=bool(stats_data.get("hiddenSubscriberCount", False)),
                    video_count=int(stats_data.get("videoCount", 0))
                ),
                extracted_at=datetime.utcnow()
            )
        except HttpError as e:
            logger.error(f"Error fetching channel: {e}")
            return self._generate_mock_channel(channel_identifier)

    def get_channel_videos(self, channel_id: str, max_results: int = 20) -> List[Video]:
        """Fetch recent videos for a channel."""
        if not self.is_configured:
            logger.info("No YouTube API Key provided. Returning sample videos.")
            return self._generate_mock_videos(channel_id, count=max_results)

        try:
            # 1. Search for channel videos
            search_request = self._service.search().list(
                part="id",
                channelId=channel_id,
                maxResults=min(max_results, 50),
                order="date",
                type="video"
            )
            search_response = search_request.execute()
            video_ids = [item["id"]["videoId"] for item in search_response.get("items", []) if "videoId" in item.get("id", {})]

            if not video_ids:
                return []

            # 2. Get detailed video statistics & contentDetails
            videos_request = self._service.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(video_ids)
            )
            videos_response = videos_request.execute()

            videos = []
            for item in videos_response.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                content_details = item.get("contentDetails", {})

                videos.append(
                    Video(
                        video_id=item["id"],
                        snippet=VideoSnippet(
                            title=snippet.get("title", ""),
                            description=snippet.get("description", ""),
                            published_at=datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00")),
                            channel_id=snippet.get("channelId", channel_id),
                            channel_title=snippet.get("channelTitle", ""),
                            thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url"),
                            tags=snippet.get("tags", []),
                            category_id=snippet.get("categoryId")
                        ),
                        statistics=VideoStatistics(
                            view_count=int(stats.get("viewCount", 0)),
                            like_count=int(stats.get("likeCount", 0)),
                            comment_count=int(stats.get("commentCount", 0))
                        ),
                        duration=content_details.get("duration"),
                        extracted_at=datetime.utcnow()
                    )
                )
            return videos
        except HttpError as e:
            logger.error(f"Error fetching channel videos: {e}")
            return self._generate_mock_videos(channel_id, count=max_results)

    def _generate_mock_channel(self, identifier: str) -> Channel:
        name = identifier.lstrip("@") if identifier.startswith("@") else "TechPlatformDemo"
        return Channel(
            channel_id="UC_demo_" + name.lower(),
            snippet=ChannelSnippet(
                title=f"{name.capitalize()} Analytics Channel",
                description="Demo channel for YouTube Analytics Platform showcasing GCP data ingestion.",
                custom_url=f"@{name.lower()}",
                published_at=datetime.utcnow() - timedelta(days=730),
                thumbnail_url="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=200",
                country="US"
            ),
            statistics=ChannelStatistics(
                view_count=1854200,
                subscriber_count=48500,
                hidden_subscriber_count=False,
                video_count=142
            ),
            extracted_at=datetime.utcnow()
        )

    def _generate_mock_videos(self, channel_id: str, count: int = 10) -> List[Video]:
        sample_topics = [
            ("Mastering Cloud Run in 15 Minutes", 34200, 1850, 210),
            ("BigQuery Best Practices for Cost & Speed", 62100, 3120, 480),
            ("Building Autonomous AI Agents with Python", 98500, 5600, 789),
            ("YouTube Analytics Pipeline Architecture", 24300, 1200, 145),
            ("Dataflow vs Cloud Functions: Deep Dive", 41900, 2300, 310),
            ("Deploying Serverless Microservices on GCP", 53100, 2900, 395),
            ("Real-Time Event Streaming with Pub/Sub", 38700, 1950, 260),
            ("Secure GCP IAM & Service Account Secrets", 29800, 1420, 190),
            ("Kubernetes Engine (GKE) Production Checklist", 71400, 3900, 520),
            ("Optimizing Cloud SQL & AlloyDB Queries", 45600, 2450, 315)
        ]
        videos = []
        now = datetime.utcnow()
        for idx in range(min(count, len(sample_topics))):
            title, views, likes, comments = sample_topics[idx]
            videos.append(
                Video(
                    video_id=f"demo_vid_{idx + 1:03d}",
                    snippet=VideoSnippet(
                        title=title,
                        description=f"Detailed walkthrough on {title}. Learn modern GCP data engineering techniques.",
                        published_at=now - timedelta(days=(idx + 1) * 6),
                        channel_id=channel_id,
                        channel_title="Demo Tech Channel",
                        thumbnail_url="https://images.unsplash.com/photo-1518770660439-4636190af475?w=400",
                        tags=["GCP", "Cloud", "Analytics", "Data Engineering"],
                        category_id="28"
                    ),
                    statistics=VideoStatistics(
                        view_count=views,
                        like_count=likes,
                        comment_count=comments
                    ),
                    duration="PT14M32S",
                    extracted_at=now
                )
            )
        return videos
