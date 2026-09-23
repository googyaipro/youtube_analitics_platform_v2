from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import get_current_user, decrypt_secret
from backend.models.user import User
from backend.models.channel_set import ChannelSet
from backend.models.channel import Channel
from backend.schemas.channel_set import ChannelSetCreate, ChannelSetUpdate, ChannelSetResponse
from backend.services.scheduler_service import SchedulerService
from backend.services.analytics_service import AnalyticsService
from backend.services.gemini_service import GeminiService

router = APIRouter(prefix="/channel-sets", tags=["Channel Sets & Custom Scheduler"])


@router.get("", response_model=List[ChannelSetResponse])
def list_channel_sets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all channel sets for authenticated user."""
    sets = db.query(ChannelSet).filter(ChannelSet.user_id == current_user.id).order_by(ChannelSet.created_at.desc()).all()
    results = []
    for s in sets:
        count = db.query(Channel).filter(Channel.set_id == s.id).count()
        results.append(ChannelSetResponse(
            id=s.id,
            user_id=s.user_id,
            name=s.name,
            description=s.description,
            schedule_time=s.schedule_time,
            schedule_timezone=s.schedule_timezone,
            schedule_days=s.schedule_days,
            schedule_enabled=s.schedule_enabled,
            last_run_at=s.last_run_at,
            channel_count=count,
            created_at=s.created_at
        ))
    return results


@router.post("", response_model=ChannelSetResponse, status_code=status.HTTP_201_CREATED)
def create_channel_set(
    set_in: ChannelSetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new channel set with customized schedule."""
    new_set = ChannelSet(
        user_id=current_user.id,
        name=set_in.name,
        description=set_in.description,
        schedule_time=set_in.schedule_time,
        schedule_timezone=set_in.schedule_timezone,
        schedule_days=set_in.schedule_days,
        schedule_enabled=set_in.schedule_enabled
    )
    db.add(new_set)
    db.commit()
    db.refresh(new_set)

    if not current_user.active_set_id:
        current_user.active_set_id = new_set.id
        db.commit()

    return ChannelSetResponse(
        id=new_set.id,
        user_id=new_set.user_id,
        name=new_set.name,
        description=new_set.description,
        schedule_time=new_set.schedule_time,
        schedule_timezone=new_set.schedule_timezone,
        schedule_days=new_set.schedule_days,
        schedule_enabled=new_set.schedule_enabled,
        last_run_at=new_set.last_run_at,
        channel_count=0,
        created_at=new_set.created_at
    )


@router.get("/{set_id}", response_model=ChannelSetResponse)
def get_channel_set(
    set_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get single channel set details."""
    c_set = db.query(ChannelSet).filter(ChannelSet.id == set_id, ChannelSet.user_id == current_user.id).first()
    if not c_set:
        raise HTTPException(status_code=404, detail="Channel set not found.")

    count = db.query(Channel).filter(Channel.set_id == c_set.id).count()
    return ChannelSetResponse(
        id=c_set.id,
        user_id=c_set.user_id,
        name=c_set.name,
        description=c_set.description,
        schedule_time=c_set.schedule_time,
        schedule_timezone=c_set.schedule_timezone,
        schedule_days=c_set.schedule_days,
        schedule_enabled=c_set.schedule_enabled,
        last_run_at=c_set.last_run_at,
        channel_count=count,
        created_at=c_set.created_at
    )


@router.put("/{set_id}", response_model=ChannelSetResponse)
def update_channel_set(
    set_id: str,
    set_in: ChannelSetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update channel set attributes or scheduler configuration."""
    c_set = db.query(ChannelSet).filter(ChannelSet.id == set_id, ChannelSet.user_id == current_user.id).first()
    if not c_set:
        raise HTTPException(status_code=404, detail="Channel set not found.")

    if set_in.name is not None:
        c_set.name = set_in.name
    if set_in.description is not None:
        c_set.description = set_in.description
    if set_in.schedule_time is not None:
        c_set.schedule_time = set_in.schedule_time
    if set_in.schedule_timezone is not None:
        c_set.schedule_timezone = set_in.schedule_timezone
    if set_in.schedule_days is not None:
        c_set.schedule_days = set_in.schedule_days
    if set_in.schedule_enabled is not None:
        c_set.schedule_enabled = set_in.schedule_enabled

    db.commit()
    db.refresh(c_set)

    count = db.query(Channel).filter(Channel.set_id == c_set.id).count()
    return ChannelSetResponse(
        id=c_set.id,
        user_id=c_set.user_id,
        name=c_set.name,
        description=c_set.description,
        schedule_time=c_set.schedule_time,
        schedule_timezone=c_set.schedule_timezone,
        schedule_days=c_set.schedule_days,
        schedule_enabled=c_set.schedule_enabled,
        last_run_at=c_set.last_run_at,
        channel_count=count,
        created_at=c_set.created_at
    )


@router.delete("/{set_id}")
def delete_channel_set(
    set_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a channel set and all its associated channels and video metrics."""
    c_set = db.query(ChannelSet).filter(ChannelSet.id == set_id, ChannelSet.user_id == current_user.id).first()
    if not c_set:
        raise HTTPException(status_code=404, detail="Channel set not found.")

    db.delete(c_set)
    if current_user.active_set_id == set_id:
        other_set = db.query(ChannelSet).filter(ChannelSet.user_id == current_user.id, ChannelSet.id != set_id).first()
        current_user.active_set_id = other_set.id if other_set else None

    db.commit()
    return {"status": "SUCCESS", "message": f"Channel set {set_id} deleted."}


@router.post("/{set_id}/activate")
def activate_channel_set(
    set_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Switch active channel set for the current user."""
    c_set = db.query(ChannelSet).filter(ChannelSet.id == set_id, ChannelSet.user_id == current_user.id).first()
    if not c_set:
        raise HTTPException(status_code=404, detail="Channel set not found.")

    current_user.active_set_id = c_set.id
    db.commit()
    return {"status": "SUCCESS", "active_set_id": c_set.id, "name": c_set.name}


@router.post("/{set_id}/sync")
def sync_channel_set(
    set_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually trigger data sync for a channel set."""
    c_set = db.query(ChannelSet).filter(ChannelSet.id == set_id, ChannelSet.user_id == current_user.id).first()
    if not c_set:
        raise HTTPException(status_code=404, detail="Channel set not found.")

    count = SchedulerService.sync_channel_set_data(db, current_user, c_set)
    return {"status": "SUCCESS", "snapshots_synced": count}


@router.get("/{set_id}/digest")
def get_channel_set_digest(
    set_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate or retrieve high-level executive AI daily digest for a channel set."""
    c_set = db.query(ChannelSet).filter(ChannelSet.id == set_id, ChannelSet.user_id == current_user.id).first()
    if not c_set:
        raise HTTPException(status_code=404, detail="Channel set not found.")

    enriched_videos = AnalyticsService.get_set_enriched_videos(db, current_user.id, set_id, limit=15)
    channels = db.query(Channel).filter(Channel.user_id == current_user.id, Channel.set_id == set_id).all()
    channels_summary = [{"title": c.title, "subscriber_count": c.subscriber_count} for c in channels]

    anomalies = []
    for v in enriched_videos:
        if v.get("outlier_score", 1.0) >= 1.8:
            anomalies.append(f"Канал {v.get('channel_title')}: «{v.get('title')}» — {v.get('view_count', 0):,} просмотров ({v.get('outlier_score')}x)")

    gemini_key = decrypt_secret(current_user.gemini_api_key_encrypted)
    digest_text = GeminiService.generate_daily_digest(
        set_name=c_set.name,
        channels_summary=channels_summary,
        top_videos=enriched_videos,
        anomalies=anomalies,
        target_language=current_user.language or "ru",
        gemini_api_key=gemini_key
    )
    return {"set_id": set_id, "set_name": c_set.name, "digest": digest_text}
