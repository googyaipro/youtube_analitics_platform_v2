from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AdminUserListItem(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    language: str = "en"
    is_active: bool = True
    is_admin: bool = False
    has_youtube_key: bool = False
    has_gemini_key: bool = False
    youtube_api_key_valid: bool = False
    gemini_api_key_valid: bool = False
    telegram_chat_id: Optional[str] = None
    channel_sets_count: int = 0
    channels_count: int = 0
    created_at: datetime


class AdminStats(BaseModel):
    total_users: int = 0
    active_users: int = 0
    blocked_users: int = 0
    admin_users: int = 0
    total_channel_sets: int = 0
    total_channels: int = 0


class AdminActionResponse(BaseModel):
    success: bool
    message: str
    user_id: str
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class AdminClaimRequest(BaseModel):
    admin_secret: str = Field(..., min_length=1, description="Admin secret key")
