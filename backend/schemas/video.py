from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class VideoResponse(BaseModel):
    id: str
    video_id: str
    channel_id: str
    channel_title: str
    title: str
    description: Optional[str] = None
    view_count: int
    like_count: int
    comment_count: int
    duration: Optional[str] = None
    thumbnail_url: Optional[str] = None
    published_at: datetime
    
    # Computed virality factors
    channel_avg_views: int = 0
    outlier_score: float = 1.0
    velocity_vph: float = 0.0
    engagement_rate_pct: float = 0.0
    badges: List[str] = []


class FactorExplanation(BaseModel):
    verdict: str
    hook_analysis: str
    trend_alignment: str
    engagement_factor: str
    actionable_takeaway: str


class AnalyzeRequest(BaseModel):
    query: str
    set_id: Optional[str] = None
    target_language: Optional[str] = None


class AnalyzeResponse(BaseModel):
    answer: str
    key_findings: List[str] = []
    plotly_spec: Optional[Dict[str, Any]] = None
