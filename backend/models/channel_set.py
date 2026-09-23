import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.core.database import Base


class ChannelSet(Base):
    __tablename__ = "channel_sets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)

    # Custom User-Defined Scheduler
    schedule_time = Column(String(10), default="12:00")  # HH:MM format
    schedule_timezone = Column(String(64), default="Europe/Helsinki")
    schedule_days = Column(String(64), default="mon,tue,wed,thu,fri,sat,sun")
    schedule_enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="channel_sets")
    channels = relationship("Channel", back_populates="channel_set", cascade="all, delete-orphan")
    videos = relationship("VideoMetric", back_populates="channel_set", cascade="all, delete-orphan")
