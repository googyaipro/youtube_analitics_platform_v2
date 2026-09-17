import logging
import re
from typing import Any, Dict, List, Literal, Optional
from backend.services.bigquery_service import BigQueryService
from backend.services.firestore_cache import FirestoreCache
from backend.services.gemini_service import GeminiService
from backend.services.sandbox_client import SandboxClient
from backend.services.youtube_client import YouTubeClient

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self):
        self.yt = YouTubeClient()
        self.bq = BigQueryService()
        self.cache = FirestoreCache()
        self.gemini = GeminiService()
        self.sandbox = SandboxClient()

    def process_query(
        self,
        user_text: str,
        output_format: Literal["matplotlib", "plotly"] = "matplotlib"
    ) -> Dict[str, Any]:
        """
        End-to-end processing pipeline:
        1. Extract channel identifier from query
        2. Quota-optimized video fetch (UU... playlistItems)
        3. Gemini analytical reasoning + code generation
        4. Sandbox execution (PNG for Telegram / Plotly JSON for Web)
        """
        # 1. Detect channel handle or name in query
        channel_identifier = self._extract_channel(user_text)
        logger.info(f"Processing query '{user_text}' for channel '{channel_identifier}'")

        # 2. Fetch channel and latest videos (cached & 1 unit quota)
        channel = self.yt.get_channel(channel_identifier)
        channel_title = channel.snippet.title if channel else channel_identifier
        channel_id = channel.channel_id if channel else "UC_unknown"

        videos = self.yt.get_channel_uploads(channel_id, max_results=8)
        videos_data = [
            {
                "title": v.snippet.title,
                "view_count": v.statistics.view_count,
                "like_count": v.statistics.like_count,
                "comment_count": v.statistics.comment_count,
                "published_at": v.snippet.published_at.strftime("%Y-%m-%d")
            }
            for v in videos
        ]

        # 3. Gemini reasoning & code generation
        report = self.gemini.analyze_videos(
            channel_title=channel_title,
            videos_data=videos_data,
            user_query=user_text
        )

        # 4. Sandbox code execution
        code_to_run = report.matplotlib_code if output_format == "matplotlib" else report.plotly_code
        exec_result = self.sandbox.execute(
            code=code_to_run,
            data=videos_data,
            output_format=output_format
        )

        return {
            "channel_title": channel_title,
            "summary_text": report.summary_text,
            "key_findings": report.key_findings,
            "anomalies_detected": report.anomalies_detected,
            "png_base64": exec_result.get("png_base64"),
            "plotly_spec": exec_result.get("plotly_spec"),
            "videos_analyzed": len(videos_data),
            "execution_time_ms": exec_result.get("execution_time_ms", 0.0)
        }

    def _extract_channel(self, text: str) -> str:
        # 1. Search for explicit @handle
        handle_match = re.search(r"@[A-Za-z0-9_.-]+", text)
        if handle_match:
            return handle_match.group(0)

        # 2. Check against active tracked channels in BigQuery
        lowered = text.lower()
        try:
            channels = self.bq.get_channels()
            if channels:
                # Direct match by title or custom_url handle
                for c in channels:
                    title = (c.get("title") or "").lower()
                    custom_url = (c.get("custom_url") or "").lower().lstrip("@")
                    if (title and title in lowered) or (custom_url and custom_url in lowered):
                        return c.get("custom_url") or c.get("channel_id")

                # Keyword match by significant title words (e.g., "мастодонт", "иишенка", "goldie", "roberts")
                for c in channels:
                    title_words = [w for w in (c.get("title") or "").lower().split() if len(w) > 3]
                    if any(w in lowered for w in title_words):
                        return c.get("custom_url") or c.get("channel_id")

                # If the user asked an analytical question without naming a channel, default to the top tracked channel
                top_channel = channels[0]
                return top_channel.get("custom_url") or top_channel.get("channel_id")
        except Exception as e:
            logger.warning(f"Error querying tracked channels in orchestrator: {e}")

        # 3. Fallback for common creator names
        if "mkbhd" in lowered or "marques" in lowered:
            return "@MKBHD"
        if "beast" in lowered:
            return "@MrBeast"
        if "veritasium" in lowered:
            return "@veritasium"

        # 4. Default active competitor fallback
        return "@juliangoldieseo"
