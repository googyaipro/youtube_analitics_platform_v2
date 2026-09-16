from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Depends
from backend.services.bigquery_service import BigQueryService

router = APIRouter(prefix="/channels", tags=["Channels"])

def get_bq_service():
    return BigQueryService()

@router.get("", response_model=List[Dict[str, Any]])
def list_channels(bq: BigQueryService = Depends(get_bq_service)):
    """List all tracked YouTube channels in the platform."""
    return bq.get_channels()

@router.get("/{channel_id}", response_model=Dict[str, Any])
def get_channel(channel_id: str, bq: BigQueryService = Depends(get_bq_service)):
    """Retrieve detailed analytics for a specific channel."""
    channels = bq.get_channels()
    for c in channels:
        if c.get("channel_id") == channel_id:
            return c
    raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found in repository.")
