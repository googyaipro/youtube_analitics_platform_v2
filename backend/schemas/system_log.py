from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AILogItem(BaseModel):
    id: str
    created_at: datetime
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    operation: str
    target_id: Optional[str] = None
    target_title: Optional[str] = None
    model: str
    status: str
    http_status: Optional[int] = None
    latency_ms: int = 0
    prompt: Optional[str] = None
    raw_response: Optional[str] = None
    parsed_output: Optional[str] = None
    error_message: Optional[str] = None
    fallback_reason: Optional[str] = None

    class Config:
        from_attributes = True


class SystemLogItem(BaseModel):
    id: str
    created_at: datetime
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    category: str
    level: str
    action: str
    message: str
    details: Optional[str] = None

    class Config:
        from_attributes = True


class AILogStats(BaseModel):
    total_calls: int = 0
    success_count: int = 0
    error_count: int = 0
    fallback_count: int = 0
    avg_latency_ms: float = 0.0


class LogsOverview(BaseModel):
    ai_stats: AILogStats
    recent_ai_logs: List[AILogItem] = []
    recent_system_logs: List[SystemLogItem] = []


class ClearLogsRequest(BaseModel):
    log_type: str = Field("all", description="'ai', 'system', or 'all'")
