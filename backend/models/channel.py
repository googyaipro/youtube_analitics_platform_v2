import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.core.database import Base


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    set_id = Column(String(36), ForeignKey("channel_sets.id", ondelete="CASCADE"), index=True, nullable=False)
    
    channel_id = Column(String(64), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    custom_url = Column(String(255), nullable=True)
    description = Column(String(2048), nullable=True)
    
    subscriber_count = Column(BigInteger, default=0)
    view_count = Column(BigInteger, default=0)
    video_count = Column(Integer, default=0)
    
    country = Column(String(10), nullable=True)
    thumbnail_url = Column(String(512), nullable=True)
    published_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="channels")
    channel_set = relationship("ChannelSet", back_populates="channels")
