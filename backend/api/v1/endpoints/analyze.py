import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.services.agent_orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["AI Analyst"])

agent = AgentOrchestrator()


class AnalyzeRequest(BaseModel):
    query: str = Field(..., description="Natural language question, e.g. 'Compare views for @MKBHD'")
    channel_id: Optional[str] = Field(None, description="Optional channel ID context")


class AnalyzeResponse(BaseModel):
    channel_title: str
    summary_text: str
    key_findings: List[str]
    anomalies_detected: bool
    plotly_spec: Optional[Dict[str, Any]] = None
    videos_analyzed: int
    execution_time_ms: float


@router.post("", response_model=AnalyzeResponse)
def analyze_query(payload: AnalyzeRequest):
    """
    AI Analyst endpoint for Streamlit dashboard.
    Returns markdown text findings + interactive Plotly JSON chart specification.
    """
    result = agent.process_query(user_text=payload.query, output_format="plotly")
    return AnalyzeResponse(
        channel_title=result.get("channel_title", "Analytics"),
        summary_text=result.get("summary_text", ""),
        key_findings=result.get("key_findings", []),
        anomalies_detected=result.get("anomalies_detected", False),
        plotly_spec=result.get("plotly_spec"),
        videos_analyzed=result.get("videos_analyzed", 0),
        execution_time_ms=result.get("execution_time_ms", 0.0)
    )
