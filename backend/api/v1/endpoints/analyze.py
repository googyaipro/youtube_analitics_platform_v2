import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import get_current_user, decrypt_secret
from backend.models.user import User
from backend.models.channel_set import ChannelSet
from backend.schemas.video import AnalyzeRequest, AnalyzeResponse
from backend.services.analytics_service import AnalyticsService
from backend.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["AI Analyst"])


@router.post("", response_model=AnalyzeResponse)
def analyze_query(
    payload: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    AI Analyst interactive query endpoint.
    Answers strategic, comparative, or diagnostic questions about videos in the user's channel set.
    """
    target_set_id = payload.set_id or current_user.active_set_id
    if not target_set_id:
        first_set = db.query(ChannelSet).filter(ChannelSet.user_id == current_user.id).first()
        if first_set:
            target_set_id = first_set.id

    videos = []
    if target_set_id:
        videos = AnalyticsService.get_set_enriched_videos(db, current_user.id, target_set_id, limit=20)

    gemini_key = decrypt_secret(current_user.gemini_api_key_encrypted)
    target_lang = payload.target_language or current_user.language or "ru"

    result = GeminiService.ask_analyst(
        query=payload.query,
        videos_context=videos,
        target_language=target_lang,
        gemini_api_key=gemini_key
    )

    # Optional plotly spec if we have video data
    plotly_spec = None
    if videos:
        top_vids = sorted(videos[:6], key=lambda x: x.get("view_count", 0), reverse=True)
        plotly_spec = {
            "data": [
                {
                    "x": [v.get("title", "")[:25] + "..." for v in top_vids],
                    "y": [v.get("view_count", 0) for v in top_vids],
                    "type": "bar",
                    "marker": {"color": "#3B82F6"}
                }
            ],
            "layout": {
                "title": "Сравнение просмотров (Топ видео)",
                "xaxis": {"tickangle": -20},
                "yaxis": {"title": "Просмотры"},
                "margin": {"b": 100}
            }
        }

    return AnalyzeResponse(
        answer=result.get("answer", "Нет ответа"),
        key_findings=result.get("key_findings", []),
        plotly_spec=plotly_spec
    )
