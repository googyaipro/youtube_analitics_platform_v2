from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AddChannelRequest(BaseModel):
    channel_url_or_handle: str = Field(
        ...,
        min_length=2,
        description="YouTube handle (@channel), custom URL, or 24-character Channel ID"
    )


class ChannelResponse(BaseModel):
    id: str
    set_id: str
    channel_id: str
    title: str
    custom_url: Optional[str] = None
    description: Optional[str] = None
    subscriber_count: int = 0
    view_count: int = 0
    video_count: int = 0
    country: Optional[str] = None
    thumbnail_url: Optional[str] = None
    updated_at: datetime
