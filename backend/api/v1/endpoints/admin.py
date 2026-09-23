import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import get_current_user, get_current_admin_user
from backend.models.user import User
from backend.models.channel_set import ChannelSet
from backend.models.channel import Channel
from backend.schemas.admin import (
    AdminUserListItem,
    AdminStats,
    AdminActionResponse,
    AdminClaimRequest
)
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.post("/claim", response_model=AdminActionResponse)
def claim_admin(
    payload: AdminClaimRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Authorize current user as Administrator by verifying the ADMIN_SECRET.
    Allows platform owner to claim admin rights immediately.
    """
    admin_secret = settings.ADMIN_SECRET or "yap_admin_secret_2026"
    if payload.admin_secret.strip() != admin_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin secret key."
        )

    current_user.is_admin = True
    db.commit()
    db.refresh(current_user)

    logger.info(f"User {current_user.email} claimed administrator privileges.")
    return AdminActionResponse(
        success=True,
        message="Administrator privileges granted successfully.",
        user_id=current_user.id,
        is_admin=True,
        is_active=current_user.is_active
    )


@router.get("/stats", response_model=AdminStats)
def get_admin_stats(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Retrieve high-level system usage statistics for admin dashboard."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    blocked_users = db.query(User).filter(User.is_active == False).count()
    admin_users = db.query(User).filter(User.is_admin == True).count()
    total_sets = db.query(ChannelSet).count()
    total_channels = db.query(Channel).count()

    return AdminStats(
        total_users=total_users,
        active_users=active_users,
        blocked_users=blocked_users,
        admin_users=admin_users,
        total_channel_sets=total_sets,
        total_channels=total_channels
    )


@router.get("/users", response_model=List[AdminUserListItem])
def list_users(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List all registered users along with their usage and BYOK status."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    results = []

    for u in users:
        sets_count = db.query(ChannelSet).filter(ChannelSet.user_id == u.id).count()
        channels_count = db.query(Channel).filter(Channel.user_id == u.id).count()

        results.append(
            AdminUserListItem(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                language=u.language or "en",
                is_active=bool(u.is_active),
                is_admin=bool(u.is_admin),
                has_youtube_key=bool(u.youtube_api_key_encrypted),
                has_gemini_key=bool(u.gemini_api_key_encrypted),
                youtube_api_key_valid=bool(u.youtube_api_key_valid),
                gemini_api_key_valid=bool(u.gemini_api_key_valid),
                telegram_chat_id=u.telegram_chat_id,
                channel_sets_count=sets_count,
                channels_count=channels_count,
                created_at=u.created_at
            )
        )

    return results


@router.post("/users/{user_id}/toggle-active", response_model=AdminActionResponse)
def toggle_user_active(
    user_id: str,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Block or unblock a user (toggle is_active)."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot block your own administrator account."
        )

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    target_user.is_active = not target_user.is_active
    db.commit()
    db.refresh(target_user)

    action_name = "unblocked" if target_user.is_active else "blocked"
    logger.info(f"Admin {admin.email} {action_name} user {target_user.email}")

    return AdminActionResponse(
        success=True,
        message=f"User {target_user.email} successfully {action_name}.",
        user_id=target_user.id,
        is_active=target_user.is_active,
        is_admin=target_user.is_admin
    )


@router.post("/users/{user_id}/toggle-admin", response_model=AdminActionResponse)
def toggle_user_admin(
    user_id: str,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Promote or demote user administrator role."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove admin role from your own account."
        )

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    target_user.is_admin = not target_user.is_admin
    db.commit()
    db.refresh(target_user)

    role_str = "promoted to Admin" if target_user.is_admin else "demoted to regular User"
    logger.info(f"Admin {admin.email} {role_str} for {target_user.email}")

    return AdminActionResponse(
        success=True,
        message=f"User {target_user.email} {role_str}.",
        user_id=target_user.id,
        is_active=target_user.is_active,
        is_admin=target_user.is_admin
    )


@router.delete("/users/{user_id}", response_model=AdminActionResponse)
def delete_user(
    user_id: str,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a user account and cascade delete all their channel sets, channels, and metrics."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own administrator account."
        )

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user_email = target_user.email
    db.delete(target_user)
    db.commit()

    logger.info(f"Admin {admin.email} deleted user {user_email} (ID: {user_id})")

    return AdminActionResponse(
        success=True,
        message=f"User {user_email} and all associated data permanently deleted.",
        user_id=user_id
    )
