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

@router.get("/{video_id}/explain", response_model=Dict[str, Any])
def explain_video(video_id: str, bq: BigQueryService = Depends(get_bq_service)):
    """Explain success drivers of a specific video using Gemini 3.8 Flash and BigQuery metrics."""
    video = bq.get_video_by_id_or_title(video_id)
    if not video:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Video not found")

    from backend.services.gemini_service import GeminiService
    gemini = GeminiService()
    explanation = gemini.explain_video_success(video)

    return {
        "video_id": video.get("video_id"),
        "title": video.get("title"),
        "channel_title": video.get("channel_title"),
        "thumbnail_url": video.get("thumbnail_url"),
        "metrics": {
            "view_count": video.get("view_count", 0),
            "like_count": video.get("like_count", 0),
            "comment_count": video.get("comment_count", 0),
            "channel_avg_views": video.get("channel_avg_views", 0),
            "outlier_score": video.get("outlier_score", 1.0),
            "velocity_vph": video.get("velocity_vph", 0.0),
            "engagement_rate_pct": video.get("engagement_rate_pct", 0.0),
            "published_at": str(video.get("published_at"))
        },
        "badges": video.get("badges", []),
        "explanation": explanation
    }
