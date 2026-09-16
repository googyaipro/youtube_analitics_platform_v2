import logging
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.bigquery_service import BigQueryService
from backend.services.youtube_client import YouTubeClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/competitors", tags=["Competitor Management"])

bq = BigQueryService()
yt = YouTubeClient()


class AddCompetitorRequest(BaseModel):
    channel_url_or_handle: str = Field(..., description="Handle (e.g. @mkbhd) or Channel URL or ID")
    notes: str = Field("", description="Optional notes/category for competitor")


@router.get("", response_model=List[Dict[str, Any]])
def list_competitors():
    """List all tracked competitor channels."""
    return bq.get_channels()


@router.post("", response_model=Dict[str, Any])
def add_competitor(payload: AddCompetitorRequest):
    """Validate channel via YouTube API and register in BigQuery competitor list."""
    channel = yt.get_channel(payload.channel_url_or_handle.strip())
    if not channel:
        raise HTTPException(
            status_code=404,
            detail=f"Could not find YouTube channel for '{payload.channel_url_or_handle}'"
        )

    # Insert channel into BigQuery
    bq.insert_channel(channel)
    
    # Also fetch initial uploads snapshot
    videos = yt.get_channel_uploads(channel.channel_id, max_results=10)
    if videos:
        bq.insert_videos(videos)

    return {
        "status": "REGISTERED",
        "channel_id": channel.channel_id,
        "title": channel.snippet.title,
        "subscriber_count": channel.statistics.subscriber_count,
        "view_count": channel.statistics.view_count,
        "video_count": channel.statistics.video_count
    }


@router.delete("/{channel_id}", response_model=Dict[str, Any])
def delete_competitor(channel_id: str):
    """Remove a channel from the competitor tracking registry."""
    success = bq.delete_channel(channel_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete channel from registry.")
    return {"status": "DELETED", "channel_id": channel_id}

