import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.models.channel import Channel, ChannelSnippet, ChannelStatistics
from backend.models.video import Video, VideoSnippet, VideoStatistics
from backend.services.firestore_cache import FirestoreCache
from config.settings import get_settings

logger = logging.getLogger(__name__)


class YouTubeClient:
    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.YOUTUBE_API_KEY
        self.cache = FirestoreCache()
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

    @staticmethod
    def get_uploads_playlist_id(channel_id: str) -> str:
        """Converts Channel ID (UC...) to its Uploads Playlist ID (UU...)."""
        if channel_id.startswith("UC") and len(channel_id) > 2:
            return "UU" + channel_id[2:]
        return channel_id

    def get_channel(self, channel_identifier: str) -> Optional[Channel]:
        """Fetch channel metadata by channel ID or handle with 24h caching."""
        cache_key = f"channel_{hashlib.md5(channel_identifier.encode()).hexdigest()}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return Channel(**cached_data)

        if not self.is_configured:
            logger.info("No YouTube API Key. Generating mock channel.")
            channel = self._generate_mock_channel(channel_identifier)
            self.cache.set(cache_key, channel.model_dump())
            return channel

        try:
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

            channel = Channel(
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

            # Store in hot cache
            self.cache.set(cache_key, channel.model_dump(), ttl_hours=24)
            return channel

        except HttpError as e:
            logger.error(f"Error fetching channel: {e}")
            return self._generate_mock_channel(channel_identifier)

    def get_channel_uploads(self, channel_id: str, max_results: int = 20) -> List[Video]:
        """
        Quota-optimized video fetching:
        Uses the channel's Uploads Playlist (UU...) via playlistItems().list
        Cost: 1 unit (instead of 100 units with search().list)!
        """
        cache_key = f"uploads_{channel_id}_{max_results}"
        cached_videos = self.cache.get(cache_key)
        if cached_videos:
            return [Video(**v) for v in cached_videos]

        if not self.is_configured:
            logger.info("No YouTube API Key. Returning sample videos.")
            videos = self._generate_mock_videos(channel_id, count=max_results)
            self.cache.set(cache_key, [v.model_dump() for v in videos], ttl_hours=6)
            return videos

        try:
            uploads_playlist_id = self.get_uploads_playlist_id(channel_id)
            
            # Step 1: Fetch video IDs from Uploads playlist (Cost: 1 unit)
            playlist_request = self._service.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=min(max_results, 50)
            )
            playlist_response = playlist_request.execute()
            video_ids = [
                item["contentDetails"]["videoId"]
                for item in playlist_response.get("items", [])
                if "contentDetails" in item and "videoId" in item["contentDetails"]
            ]

            if not video_ids:
                return []

            # Step 2: Batch fetch video stats & details (Cost: 1 unit)
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

            self.cache.set(cache_key, [v.model_dump() for v in videos], ttl_hours=6)
            return videos

        except HttpError as e:
            logger.error(f"Error fetching uploads: {e}")
            return self._generate_mock_videos(channel_id, count=max_results)

    def get_channel_videos(self, channel_id: str, max_results: int = 20) -> List[Video]:
        """Alias for get_channel_uploads for backwards compatibility."""
        return self.get_channel_uploads(channel_id, max_results=max_results)

    def get_multiple_channels(self, channel_ids: List[str]) -> List[Channel]:
        """Batch fetch up to 50 channels in a single API call (Cost: 1 unit)."""
        if not channel_ids or not self.is_configured:
            return [self.get_channel(cid) for cid in channel_ids if self.get_channel(cid)]

        try:
            req = self._service.channels().list(
                part="snippet,statistics",
                id=",".join(channel_ids[:50])
            )
            resp = req.execute()
            results = []
            for item in resp.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                results.append(
                    Channel(
                        channel_id=item["id"],
                        snippet=ChannelSnippet(
                            title=snippet.get("title", ""),
                            description=snippet.get("description", ""),
                            custom_url=snippet.get("customUrl"),
                            published_at=datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00")),
                            thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url"),
                            country=snippet.get("country")
                        ),
                        statistics=ChannelStatistics(
                            view_count=int(stats.get("viewCount", 0)),
                            subscriber_count=int(stats.get("subscriberCount", 0)),
                            video_count=int(stats.get("videoCount", 0))
                        ),
                        extracted_at=datetime.utcnow()
                    )
                )
            return results
        except Exception as e:
            logger.error(f"Error batch fetching channels: {e}")
            return []

    def _generate_mock_channel(self, identifier: str) -> Channel:
        name = identifier.lstrip("@") if identifier.startswith("@") else "MKBHD"
        return Channel(
            channel_id="UC_demo_" + name.lower(),
            snippet=ChannelSnippet(
                title=f"{name.upper()} Studio",
                description=f"Official channel for {name}. Technology, smartphones, gadgets, and reviews.",
                custom_url=f"@{name.lower()}",
                published_at=datetime.utcnow() - timedelta(days=1200),
                thumbnail_url="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=200",
                country="US"
            ),
            statistics=ChannelStatistics(
                view_count=4820000000,
                subscriber_count=18900000,
                hidden_subscriber_count=False,
                video_count=1650
            ),
            extracted_at=datetime.utcnow()
        )

    def _generate_mock_videos(self, channel_id: str, count: int = 10) -> List[Video]:
        sample_topics = [
            ("The State of Smartphone Cameras in 2026", 1420000, 89000, 4200),
            ("Why Foldable Phones Finally Won", 980000, 62000, 3100),
            ("Blind Smartphone Camera Test: The Truth", 2950000, 184000, 9800),
            ("Apple Vision Pro: 2 Years Later", 1230000, 71000, 4500),
            ("The Ultimate Tech Desk Setup Tour", 890000, 54000, 2400)
        ]
        videos = []
        now = datetime.utcnow()
        for idx in range(min(count, len(sample_topics))):
            title, views, likes, comments = sample_topics[idx]
            videos.append(
                Video(
                    video_id=f"vid_mock_{idx+1:03d}",
                    snippet=VideoSnippet(
                        title=title,
                        description=f"Detailed review of {title}.",
                        published_at=now - timedelta(days=(idx + 1) * 3),
                        channel_id=channel_id,
                        channel_title="Tech Studio",
                        thumbnail_url="https://images.unsplash.com/photo-1518770660439-4636190af475?w=400",
                        tags=["Tech", "Gadgets", "Smartphones", "Review"]
                    ),
                    statistics=VideoStatistics(
                        view_count=views,
                        like_count=likes,
                        comment_count=comments
                    ),
                    duration="PT12M15S",
                    extracted_at=now
                )
            )
        return videos
