import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeService:
    @staticmethod
    def verify_api_key(api_key: Optional[str]) -> Tuple[bool, str]:
        """Test YouTube Data API v3 key validity using 1-unit call."""
        if not api_key or len(api_key.strip()) < 10:
            return False, "API key is empty or too short."

        clean_key = api_key.strip()
        url = f"{YOUTUBE_API_BASE}/channels"
        params = {
            "part": "id",
            "id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",  # Google Developers Channel
            "key": clean_key
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url, params=params)
                if res.status_code == 200:
                    return True, "YouTube Data API v3 key is valid and quota is available."
                elif res.status_code in (400, 403):
                    error_data = res.json().get("error", {})
                    message = error_data.get("message", "Invalid API key or quota exceeded.")
                    return False, f"Google API Error: {message}"
                else:
                    return False, f"Unexpected response from YouTube API ({res.status_code})"
        except Exception as e:
            logger.error(f"Error verifying YouTube key: {e}")
            return False, f"Network error connecting to YouTube API: {e}"

    @staticmethod
    def resolve_channel_id(query: str, api_key: str) -> Optional[str]:
        """Resolve handle (@MrBeast), custom URL, or return 24-character Channel ID."""
        clean_q = query.strip()
        if not clean_q or not api_key:
            return None

        # 1. Direct 24-character channel ID (UC...)
        if re.match(r"^UC[\w-]{22}$", clean_q):
            return clean_q

        # Extract handle or name from URL if pasted
        handle_match = re.search(r"@([\w.-]+)", clean_q)
        handle = handle_match.group(1) if handle_match else clean_q.lstrip("@")

        url = f"{YOUTUBE_API_BASE}/channels"
        try:
            with httpx.Client(timeout=10.0) as client:
                # Try forHandle first
                res = client.get(url, params={"part": "id", "forHandle": handle, "key": api_key})
                data = res.json()
                if "items" in data and data["items"]:
                    return data["items"][0]["id"]

                # Try forUsername
                res = client.get(url, params={"part": "id", "forUsername": handle, "key": api_key})
                data = res.json()
                if "items" in data and data["items"]:
                    return data["items"][0]["id"]
        except Exception as e:
            logger.error(f"Error resolving channel {query}: {e}")

        return None

    @classmethod
    def get_channel_details(cls, query_or_handle: str, api_key: str) -> Optional[Dict[str, Any]]:
        """Resolve channel identifier (handle/URL/ID) and fetch full channel details."""
        channel_id = cls.resolve_channel_id(query_or_handle, api_key)
        if not channel_id:
            return None
        return cls.get_channel_info(channel_id, api_key)

    @staticmethod
    def get_channel_info(channel_id: str, api_key: str) -> Optional[Dict[str, Any]]:
        """Fetch channel details (snippet + statistics) using 1 quota unit."""
        url = f"{YOUTUBE_API_BASE}/channels"
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": channel_id,
            "key": api_key
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url, params=params)
                if res.status_code != 200:
                    logger.error(f"Failed to fetch channel {channel_id}: {res.text}")
                    return None
                data = res.json()
                items = data.get("items", [])
                if not items:
                    return None
                item = items[0]
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})

                published_at_str = snippet.get("publishedAt")
                published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00")) if published_at_str else None

                return {
                    "channel_id": channel_id,
                    "title": snippet.get("title", ""),
                    "custom_url": snippet.get("customUrl"),
                    "description": snippet.get("description", ""),
                    "subscriber_count": int(stats.get("subscriberCount", 0)),
                    "view_count": int(stats.get("viewCount", 0)),
                    "video_count": int(stats.get("videoCount", 0)),
                    "country": snippet.get("country"),
                    "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url") or snippet.get("thumbnails", {}).get("default", {}).get("url"),
                    "published_at": published_at,
                    "uploads_playlist_id": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                }
        except Exception as e:
            logger.error(f"Exception in get_channel_info: {e}")
            return None

    @staticmethod
    def get_channel_recent_videos(channel_id: str, api_key: str, max_results: int = 15) -> List[Dict[str, Any]]:
        """
        Fetch recent channel videos via Uploads Playlist (UU...) and video statistics.
        Cost: 2 units (1 unit for playlistItems + 1 unit for video statistics).
        """
        # Uploads playlist ID is channel_id with 'UU' replacing 'UC'
        uploads_playlist_id = "UU" + channel_id[2:] if channel_id.startswith("UC") else None
        if not uploads_playlist_id:
            return []

        # 1. Fetch playlist items
        playlist_url = f"{YOUTUBE_API_BASE}/playlistItems"
        params = {
            "part": "snippet,contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": min(max_results, 50),
            "key": api_key
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(playlist_url, params=params)
                if res.status_code != 200:
                    logger.warning(f"Failed playlistItems for {uploads_playlist_id}: {res.text}")
                    return []
                items = res.json().get("items", [])
                if not items:
                    return []

                video_ids = [item.get("contentDetails", {}).get("videoId") for item in items if item.get("contentDetails", {}).get("videoId")]
                if not video_ids:
                    return []

                # 2. Batch fetch video statistics (up to 50 videos = 1 unit)
                videos_url = f"{YOUTUBE_API_BASE}/videos"
                vid_params = {
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(video_ids),
                    "key": api_key
                }
                vid_res = client.get(videos_url, params=vid_params)
                if vid_res.status_code != 200:
                    return []

                video_items = vid_res.json().get("items", [])
                parsed_videos = []

                for v in video_items:
                    snippet = v.get("snippet", {})
                    stats = v.get("statistics", {})
                    content_details = v.get("contentDetails", {})

                    pub_str = snippet.get("publishedAt")
                    published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00")) if pub_str else datetime.now(timezone.utc)

                    parsed_videos.append({
                        "video_id": v.get("id"),
                        "channel_id": channel_id,
                        "channel_title": snippet.get("channelTitle", ""),
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "view_count": int(stats.get("viewCount", 0)),
                        "like_count": int(stats.get("likeCount", 0)),
                        "comment_count": int(stats.get("commentCount", 0)),
                        "duration": content_details.get("duration"),
                        "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url") or snippet.get("thumbnails", {}).get("default", {}).get("url"),
                        "published_at": published_at
                    })

                return parsed_videos
        except Exception as e:
            logger.error(f"Error fetching uploads for {channel_id}: {e}")
            return []
