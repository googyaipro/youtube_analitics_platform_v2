from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query, Depends
from backend.services.bigquery_service import BigQueryService

router = APIRouter(prefix="/videos", tags=["Videos"])

def get_bq_service():
    return BigQueryService()

@router.get("", response_model=List[Dict[str, Any]])
def list_videos(
    channel_id: Optional[str] = Query(None, description="Filter by YouTube Channel ID"),
    limit: int = Query(50, ge=1, le=200, description="Max videos to return"),
    bq: BigQueryService = Depends(get_bq_service)
):
    """List videos and their performance metrics."""
    return bq.get_videos(channel_id=channel_id, limit=limit)

@router.get("/kpis", response_model=Dict[str, Any])
def get_analytics_kpis(bq: BigQueryService = Depends(get_bq_service)):
    """Get aggregated metrics and performance KPIs across tracked channels."""
    return bq.get_kpis()
