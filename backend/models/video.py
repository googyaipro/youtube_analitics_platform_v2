from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class VideoSnippet(BaseModel):
    title: str
    description: Optional[str] = ""
    published_at: datetime
    channel_id: str
    channel_title: str
    thumbnail_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    category_id: Optional[str] = None


class VideoStatistics(BaseModel):
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0


class Video(BaseModel):
    video_id: str
    snippet: VideoSnippet
    statistics: VideoStatistics
    duration: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
