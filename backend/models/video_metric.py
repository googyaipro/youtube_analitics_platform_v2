import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from backend.core.database import Base


class VideoMetric(Base):
    __tablename__ = "video_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    set_id = Column(String(36), ForeignKey("channel_sets.id", ondelete="CASCADE"), index=True, nullable=False)

    video_id = Column(String(64), index=True, nullable=False)
    channel_id = Column(String(64), index=True, nullable=False)
    channel_title = Column(String(255), nullable=False)
    title = Column(String(512), nullable=False)
    description = Column(String(4096), nullable=True)

    view_count = Column(BigInteger, default=0)
    like_count = Column(BigInteger, default=0)
    comment_count = Column(BigInteger, default=0)
    duration = Column(String(32), nullable=True)
    thumbnail_url = Column(String(512), nullable=True)

    published_at = Column(DateTime, index=True, nullable=False)
    extracted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    user = relationship("User", back_populates="videos")
    channel_set = relationship("ChannelSet", back_populates="videos")

    __table_args__ = (
        Index("idx_user_set_video", "user_id", "set_id", "video_id"),
        Index("idx_user_set_channel", "user_id", "set_id", "channel_id"),
    )
