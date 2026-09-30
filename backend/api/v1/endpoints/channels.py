import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import get_current_user, decrypt_secret
from backend.models.user import User
from backend.models.channel_set import ChannelSet
from backend.models.channel import Channel
from backend.models.video_metric import VideoMetric
from backend.schemas.channel import AddChannelRequest, ChannelResponse
from backend.services.youtube_service import YouTubeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["Channels"])


@router.get("", response_model=List[ChannelResponse])
def list_channels(
    set_id: Optional[str] = Query(None, description="Channel Set ID (defaults to active set)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all tracked YouTube channels for the user in the selected channel set."""
    target_set_id = set_id or current_user.active_set_id
    if not target_set_id:
        # If user has no active set yet, find first
        first_set = db.query(ChannelSet).filter(ChannelSet.user_id == current_user.id).first()
        if first_set:
            target_set_id = first_set.id
        else:
            return []

    channels = db.query(Channel).filter(
        Channel.user_id == current_user.id,
        Channel.set_id == target_set_id
    ).order_by(Channel.subscriber_count.desc()).all()

    return channels


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
def add_channel(
    req: AddChannelRequest,
    set_id: Optional[str] = Query(None, description="Target Channel Set ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a new YouTube channel to the specified (or active) channel set.
    Uses the user's personal YouTube API key to fetch channel metadata and initial videos.
    """
    target_set_id = set_id or current_user.active_set_id
    if not target_set_id:
        # Check if user has any set, or create a default one
        c_set = db.query(ChannelSet).filter(ChannelSet.user_id == current_user.id).first()
        if not c_set:
            c_set = ChannelSet(
                user_id=current_user.id,
                name="Основной",
                description="Набор по умолчанию"
            )
            db.add(c_set)
            db.flush()
            current_user.active_set_id = c_set.id
        target_set_id = c_set.id

    yt_key = decrypt_secret(current_user.youtube_api_key_encrypted)
    if not yt_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="YouTube Data API key is not configured. Please add your API key in Profile settings first."
        )

    # Fetch channel metadata via YouTube API
    channel_info = YouTubeService.get_channel_details(req.channel_url_or_handle.strip(), yt_key)
    if not channel_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not resolve YouTube channel from identifier: '{req.channel_url_or_handle}'. Check handle or URL."
        )

    yt_channel_id = channel_info["channel_id"]

    # Check for duplicate in set
    existing = db.query(Channel).filter(
        Channel.user_id == current_user.id,
        Channel.set_id == target_set_id,
        Channel.channel_id == yt_channel_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel '{channel_info['title']}' is already in this channel set."
        )

    new_channel = Channel(
        user_id=current_user.id,
        set_id=target_set_id,
        channel_id=yt_channel_id,
        title=channel_info.get("title", ""),
        custom_url=channel_info.get("custom_url"),
        description=channel_info.get("description", "")[:2000] if channel_info.get("description") else None,
        subscriber_count=channel_info.get("subscriber_count", 0),
        view_count=channel_info.get("view_count", 0),
        video_count=channel_info.get("video_count", 0),
        country=channel_info.get("country"),
        thumbnail_url=channel_info.get("thumbnail_url"),
        published_at=channel_info.get("published_at")
    )
    db.add(new_channel)
    db.commit()
    db.refresh(new_channel)

    # Immediately fetch initial batch of recent videos for analytics
    try:
        recent_vids = YouTubeService.get_channel_recent_videos(yt_channel_id, yt_key, max_results=10)
        now = datetime.now(timezone.utc)
        for v in recent_vids:
            db.add(VideoMetric(
                user_id=current_user.id,
                set_id=target_set_id,
                video_id=v["video_id"],
                channel_id=yt_channel_id,
                channel_title=v.get("channel_title") or new_channel.title,
                title=v.get("title", ""),
                description=v.get("description", ""),
                view_count=v.get("view_count", 0),
                like_count=v.get("like_count", 0),
                comment_count=v.get("comment_count", 0),
                duration=v.get("duration"),
                thumbnail_url=v.get("thumbnail_url"),
                published_at=v.get("published_at"),
                extracted_at=now
            ))
        db.commit()
    except Exception as e:
        logger.warning(f"Error fetching initial videos for channel {yt_channel_id}: {e}")

    return new_channel


@router.delete("/{channel_id}")
def delete_channel(
    channel_id: str,
    set_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a channel and its historical video metrics from the user's set."""
    query = db.query(Channel).filter(
        Channel.user_id == current_user.id,
        (Channel.id == channel_id) | (Channel.channel_id == channel_id)
    )
    if set_id:
        query = query.filter(Channel.set_id == set_id)

    channel = query.first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found in your sets.")

    # Delete video metrics for this channel
    db.query(VideoMetric).filter(
        VideoMetric.user_id == current_user.id,
        VideoMetric.set_id == channel.set_id,
        VideoMetric.channel_id == channel.channel_id
    ).delete()

    db.delete(channel)
    db.commit()

    return {"ok": True, "message": f"Channel '{channel.title}' and its metrics removed successfully."}
