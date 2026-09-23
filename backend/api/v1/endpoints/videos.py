import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import get_current_user, decrypt_secret
from backend.models.user import User
from backend.models.channel_set import ChannelSet
from backend.models.video_metric import VideoMetric
from backend.services.analytics_service import AnalyticsService
from backend.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["Videos"])


@router.get("", response_model=List[Dict[str, Any]])
def list_videos(
    set_id: Optional[str] = Query(None, description="Channel Set ID (defaults to active set)"),
    channel_id: Optional[str] = Query(None, description="Filter by YouTube Channel ID"),
    format_filter: Optional[str] = Query("all", description="Video format: all, long, short"),
    sort_by: Optional[str] = Query("views", description="Sort by: views, outlier, vph, published_at, views_to_subs"),
    limit: int = Query(50, ge=1, le=200, description="Max videos to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List videos and enriched virality metrics (channel_avg_views, outlier_score, velocity_vph, badges)
    for the user's active or specified channel set.
    """
    target_set_id = set_id or current_user.active_set_id
    if not target_set_id:
        first_set = db.query(ChannelSet).filter(ChannelSet.user_id == current_user.id).first()
        if first_set:
            target_set_id = first_set.id
        else:
            return []

    return AnalyticsService.get_set_enriched_videos(
        db=db,
        user_id=current_user.id,
        set_id=target_set_id,
        limit=limit,
        channel_id=channel_id,
        format_filter=format_filter,
        sort_by=sort_by
    )


@router.get("/kpis", response_model=Dict[str, Any])
def get_analytics_kpis(
    set_id: Optional[str] = Query(None, description="Channel Set ID (defaults to active set)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get high-level summary KPIs (total views, viral hits, top video) for the selected channel set."""
    target_set_id = set_id or current_user.active_set_id
    if not target_set_id:
        first_set = db.query(ChannelSet).filter(ChannelSet.user_id == current_user.id).first()
        if first_set:
            target_set_id = first_set.id
        else:
            return {
                "total_channels": 0,
                "total_videos": 0,
                "total_views": 0,
                "avg_views_per_video": 0,
                "viral_hits_count": 0,
                "top_video": None
            }

    return AnalyticsService.get_set_kpis(db=db, user_id=current_user.id, set_id=target_set_id)


@router.get("/{video_id}/explain", response_model=Dict[str, Any])
def explain_video(
    video_id: str,
    set_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Explain success drivers and virality factors of a specific video using Gemini AI
    and the user's personal Gemini API key.
    """
    target_set_id = set_id or current_user.active_set_id
    if not target_set_id:
        first_set = db.query(ChannelSet).filter(ChannelSet.user_id == current_user.id).first()
        if first_set:
            target_set_id = first_set.id

    # Find video in user's datasets
    query = db.query(VideoMetric).filter(
        VideoMetric.user_id == current_user.id,
        VideoMetric.video_id == video_id
    )
    if target_set_id:
        query = query.filter(VideoMetric.set_id == target_set_id)
    
    vm = query.first()
    if not vm:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found in your tracked channels.")

    # Get enriched details
    enriched_list = AnalyticsService.get_set_enriched_videos(
        db, current_user.id, vm.set_id, limit=100, channel_id=vm.channel_id
    )
    target_video = next((v for v in enriched_list if v.get("video_id") == video_id), None)
    if not target_video:
        target_video = {
            "video_id": vm.video_id,
            "title": vm.title,
            "channel_title": vm.channel_title,
            "view_count": vm.view_count,
            "like_count": vm.like_count,
            "comment_count": vm.comment_count,
            "published_at": vm.published_at.isoformat() if vm.published_at else "",
            "thumbnail_url": vm.thumbnail_url,
            "outlier_score": 1.0,
            "velocity_vph": 0.0,
            "channel_avg_views": vm.view_count
        }

    gemini_key = decrypt_secret(current_user.gemini_api_key_encrypted)
    explanation = GeminiService.explain_video_success(
        video_data=target_video,
        target_language=current_user.language or "ru",
        gemini_api_key=gemini_key
    )

    return {
        "video_id": target_video.get("video_id"),
        "title": target_video.get("title"),
        "channel_title": target_video.get("channel_title"),
        "thumbnail_url": target_video.get("thumbnail_url"),
        "metrics": {
            "view_count": target_video.get("view_count", 0),
            "like_count": target_video.get("like_count", 0),
            "comment_count": target_video.get("comment_count", 0),
            "channel_avg_views": target_video.get("channel_avg_views", 0),
            "outlier_score": target_video.get("outlier_score", 1.0),
            "velocity_vph": target_video.get("velocity_vph", 0.0),
            "engagement_rate_pct": target_video.get("engagement_rate_pct", 0.0),
            "duration_formatted": target_video.get("duration_formatted", "--:--"),
            "format_type": target_video.get("format_type", "long"),
            "is_short": target_video.get("is_short", False),
            "subscriber_count": target_video.get("subscriber_count", 0),
            "views_to_subs_pct": target_video.get("views_to_subs_pct", 0.0),
            "published_at": str(target_video.get("published_at"))
        },
        "badges": target_video.get("badges", []),
        "explanation": explanation
    }
