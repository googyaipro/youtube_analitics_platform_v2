import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.user import User
from backend.schemas.system_log import (
    AILogItem,
    SystemLogItem,
    AILogStats,
    ClearLogsRequest
)
from backend.services.log_service import LogService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["Telemetry & Diagnostics"])


@router.get("/ai", response_model=List[AILogItem])
def get_ai_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    operation: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve AI telemetry and diagnostics.
    Administrators see logs from all users; regular users see only their own calls.
    """
    return LogService.get_ai_logs(
        db=db,
        user_id=current_user.id,
        is_admin=bool(current_user.is_admin),
        limit=limit,
        offset=offset,
        status=status,
        operation=operation,
        search=search
    )


@router.get("/ai/stats", response_model=AILogStats)
def get_ai_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve statistical breakdown of AI calls (success rate, error count, avg latency)."""
    return LogService.get_ai_stats(
        db=db,
        user_id=current_user.id,
        is_admin=bool(current_user.is_admin)
    )


@router.get("/system", response_model=List[SystemLogItem])
def get_system_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve system event logs (telegram, scheduler, sync, auth, etc.).
    Administrators see all; regular users see only their events.
    """
    return LogService.get_system_logs(
        db=db,
        user_id=current_user.id,
        is_admin=bool(current_user.is_admin),
        limit=limit,
        offset=offset,
        category=category,
        level=level,
        search=search
    )


@router.post("/clear", response_model=Dict[str, Any])
def clear_logs(
    payload: ClearLogsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Clear logs. Regular users can clear their own logs; Administrators can clear all logs.
    """
    deleted = LogService.clear_logs(
        db=db,
        log_type=payload.log_type,
        user_id=current_user.id,
        is_admin=bool(current_user.is_admin)
    )
    return {
        "success": True,
        "message": f"Successfully cleared {deleted} log entries.",
        "deleted_count": deleted
    }
