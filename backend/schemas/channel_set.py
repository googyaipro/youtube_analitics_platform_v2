from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChannelSetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    schedule_time: str = Field("12:00", pattern=r"^\d{2}:\d{2}$")
    schedule_timezone: str = "Europe/Helsinki"
    schedule_days: str = "mon,tue,wed,thu,fri,sat,sun"
    schedule_enabled: bool = True


class ChannelSetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    schedule_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    schedule_timezone: Optional[str] = None
    schedule_days: Optional[str] = None
    schedule_enabled: Optional[bool] = None


class ChannelSetResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    schedule_time: str
    schedule_timezone: str
    schedule_days: str
    schedule_enabled: bool
    last_run_at: Optional[datetime] = None
    channel_count: int = 0
    created_at: datetime
