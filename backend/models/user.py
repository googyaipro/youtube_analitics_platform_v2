import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship

from backend.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)

    # Bring Your Own Key (BYOK) - Stored encrypted
    youtube_api_key_encrypted = Column(String(512), nullable=True)
    gemini_api_key_encrypted = Column(String(512), nullable=True)
    youtube_api_key_valid = Column(Boolean, default=False)
    gemini_api_key_valid = Column(Boolean, default=False)

    # Telegram binding
    telegram_chat_id = Column(String(64), unique=True, index=True, nullable=True)
    telegram_link_code = Column(String(32), unique=True, index=True, nullable=True)

    # Preferences
    language = Column(String(10), default="en")  # en, de, fi, ru, ka
    active_set_id = Column(String(36), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    channel_sets = relationship("ChannelSet", back_populates="user", cascade="all, delete-orphan")
    channels = relationship("Channel", back_populates="user", cascade="all, delete-orphan")
    videos = relationship("VideoMetric", back_populates="user", cascade="all, delete-orphan")
