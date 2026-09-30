import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from backend.core.database import Base


class AILog(Base):
    """Detailed telemetry and audit log for every LLM / Gemini call."""
    __tablename__ = "ai_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email = Column(String(255), nullable=True, index=True)

    operation = Column(String(64), nullable=False, index=True)  # explain_video, daily_digest, ask_analyst, verify_key
    target_id = Column(String(128), nullable=True, index=True)  # e.g. video_id or channel_set_id
    target_title = Column(String(512), nullable=True)           # e.g. video title or prompt query
    model = Column(String(64), nullable=False, index=True)      # e.g. gemini-flash-latest

    status = Column(String(32), nullable=False, index=True)     # SUCCESS, ERROR, FALLBACK_RULE_BASED, PARSE_ERROR
    http_status = Column(BigInteger, nullable=True)             # 200, 400, 429, etc.
    latency_ms = Column(BigInteger, default=0)                  # round-trip duration in ms

    prompt = Column(Text, nullable=True)                        # full prompt sent to LLM
    raw_response = Column(Text, nullable=True)                  # full text returned by LLM
    parsed_output = Column(Text, nullable=True)                 # JSON representation of parsed data
    error_message = Column(Text, nullable=True)                 # error or exception trace
    fallback_reason = Column(String(512), nullable=True)        # reason why heuristic fallback was triggered

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationship
    user = relationship("User")

    __table_args__ = (
        Index("idx_ai_log_user_op", "user_id", "operation"),
        Index("idx_ai_log_status_created", "status", "created_at"),
    )


class SystemLog(Base):
    """General system event and activity log (telegram, scheduler, sync, auth)."""
    __tablename__ = "system_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)

    category = Column(String(32), nullable=False, index=True)  # ai, telegram, scheduler, sync, auth, system
    level = Column(String(16), default="INFO", index=True)      # INFO, WARNING, ERROR, CRITICAL
    action = Column(String(64), nullable=False, index=True)    # e.g. command_explain, dispatch_digests, sync_job
    message = Column(String(1024), nullable=False)
    details = Column(Text, nullable=True)                       # JSON or trace

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("idx_sys_cat_level", "category", "level"),
        Index("idx_sys_created", "created_at"),
    )
