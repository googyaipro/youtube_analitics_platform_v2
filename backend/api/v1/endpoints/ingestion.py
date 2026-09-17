from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from backend.services.youtube_client import YouTubeClient
from backend.services.bigquery_service import BigQueryService
from backend.services.storage_service import StorageService

router = APIRouter(prefix="/ingestion", tags=["Data Ingestion & Pipeline"])


class SyncRequest(BaseModel):
    channel_identifier: str = Field(..., description="Channel handle (e.g. @juliangoldieseo) or Channel ID")
    max_videos: int = Field(20, ge=1, le=100, description="Number of recent videos to ingest")


class SyncResponse(BaseModel):
    status: str
    channel_id: str
    channel_title: str
    videos_synced: int
    raw_storage_uri: str
    timestamp: datetime


def get_services():
    return YouTubeClient(), BigQueryService(), StorageService()


@router.post("/sync", response_model=SyncResponse)
def trigger_channel_sync(
    payload: SyncRequest,
    services=Depends(get_services)
):
    """
    Ingests YouTube data for a channel:
    1. Fetches channel & video metrics via YouTube Data API v3.
    2. Archives raw payload into Google Cloud Storage.
    3. Streams structured analytics into BigQuery.
    """
    yt_client, bq_service, storage_service = services

    # 1. Fetch channel info
    channel = yt_client.get_channel(payload.channel_identifier)
    if not channel:
        raise HTTPException(
            status_code=404,
            detail=f"Could not retrieve channel info for identifier: {payload.channel_identifier}"
        )

    # 2. Fetch channel videos
    videos = yt_client.get_channel_videos(channel.channel_id, max_results=payload.max_videos)

    # 3. Archive raw payload to Google Cloud Storage
    now_str = datetime.utcnow().strftime("%Y/%m/%d")
    blob_path = f"channels/{now_str}/{channel.channel_id}_raw.json"
    archive_data = {
        "channel": channel.model_dump(),
        "videos": [v.model_dump() for v in videos],
        "ingested_at": datetime.utcnow().isoformat()
    }
    storage_uri = storage_service.upload_raw_json(blob_path, archive_data)

    # 4. Stream/Upsert into BigQuery
    bq_service.insert_channel(channel)
    if videos:
        bq_service.insert_videos(videos)

    return SyncResponse(
        status="SUCCESS",
        channel_id=channel.channel_id,
        channel_title=channel.snippet.title,
        videos_synced=len(videos),
        raw_storage_uri=storage_uri,
        timestamp=datetime.utcnow()
    )
