from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChannelSnippet(BaseModel):
    title: str
    description: Optional[str] = ""
    custom_url: Optional[str] = None
    published_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    country: Optional[str] = None


class ChannelStatistics(BaseModel):
    view_count: int = 0
    subscriber_count: int = 0
    hidden_subscriber_count: bool = False
    video_count: int = 0


class Channel(BaseModel):
    channel_id: str
    snippet: ChannelSnippet
    statistics: ChannelStatistics
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
