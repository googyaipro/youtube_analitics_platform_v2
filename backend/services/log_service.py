import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, func

from backend.core.database import SessionLocal
from backend.models.system_log import AILog, SystemLog

logger = logging.getLogger(__name__)


class LogService:
    @staticmethod
    def log_ai_call(
        operation: str,
        model: str,
        status: str,
        latency_ms: int,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        target_id: Optional[str] = None,
        target_title: Optional[str] = None,
        prompt: Optional[str] = None,
        raw_response: Optional[str] = None,
        parsed_output: Optional[Any] = None,
        http_status: Optional[int] = None,
        error_message: Optional[str] = None,
        fallback_reason: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[str]:
        """
        Record telemetry for an AI / LLM call.
        Safe against database exceptions so caller execution never halts.
        """
        parsed_str = None
        if parsed_output is not None:
            if isinstance(parsed_output, (dict, list)):
                try:
                    parsed_str = json.dumps(parsed_output, ensure_ascii=False)
                except Exception:
                    parsed_str = str(parsed_output)
            else:
                parsed_str = str(parsed_output)

        close_session = False
        if db is None:
            db = SessionLocal()
            close_session = True

        try:
            entry = AILog(
                user_id=user_id,
                user_email=user_email,
                operation=operation,
                target_id=target_id,
                target_title=target_title[:500] if target_title else None,
                model=model,
                status=status,
                http_status=http_status,
                latency_ms=latency_ms,
                prompt=prompt,
                raw_response=raw_response,
                parsed_output=parsed_str,
                error_message=error_message,
                fallback_reason=fallback_reason,
                created_at=datetime.now(timezone.utc)
            )
            db.add(entry)
            db.commit()
            return entry.id
        except Exception as e:
            logger.error(f"Failed to record AI log: {e}", exc_info=False)
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            return None
        finally:
            if close_session and db:
                try:
                    db.close()
                except Exception:
                    pass

    @staticmethod
    def log_system_event(
        category: str,
        action: str,
        message: str,
        level: str = "INFO",
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        details: Optional[Any] = None,
        db: Optional[Session] = None
    ) -> Optional[str]:
        """
        Record a system event (telegram, scheduler, sync, auth, system).
        Safe against database exceptions.
        """
        det_str = None
        if details is not None:
            if isinstance(details, (dict, list)):
                try:
                    det_str = json.dumps(details, ensure_ascii=False)
                except Exception:
                    det_str = str(details)
            else:
                det_str = str(details)

        close_session = False
        if db is None:
            db = SessionLocal()
            close_session = True

        try:
            entry = SystemLog(
                user_id=user_id,
                user_email=user_email,
                category=category,
                level=level,
                action=action,
                message=message[:1000] if message else "",
                details=det_str,
                created_at=datetime.now(timezone.utc)
            )
            db.add(entry)
            db.commit()
            return entry.id
        except Exception as e:
            logger.error(f"Failed to record system log: {e}", exc_info=False)
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            return None
        finally:
            if close_session and db:
                try:
                    db.close()
                except Exception:
                    pass

    @staticmethod
    def get_ai_logs(
        db: Session,
        user_id: Optional[str] = None,
        is_admin: bool = False,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        operation: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[AILog]:
        """Query AI execution logs with optional filtering."""
        query = db.query(AILog)
        if not is_admin and user_id:
            query = query.filter(AILog.user_id == user_id)

        if status and status != "ALL":
            query = query.filter(AILog.status == status)

        if operation and operation != "ALL":
            query = query.filter(AILog.operation == operation)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    AILog.target_title.ilike(term),
                    AILog.target_id.ilike(term),
                    AILog.prompt.ilike(term),
                    AILog.raw_response.ilike(term),
                    AILog.error_message.ilike(term),
                    AILog.user_email.ilike(term)
                )
            )

        return query.order_by(desc(AILog.created_at)).offset(offset).limit(limit).all()

    @staticmethod
    def get_system_logs(
        db: Session,
        user_id: Optional[str] = None,
        is_admin: bool = False,
        limit: int = 50,
        offset: int = 0,
        category: Optional[str] = None,
        level: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[SystemLog]:
        """Query general system events."""
        query = db.query(SystemLog)
        if not is_admin and user_id:
            query = query.filter(SystemLog.user_id == user_id)

        if category and category != "ALL":
            query = query.filter(SystemLog.category == category)

        if level and level != "ALL":
            query = query.filter(SystemLog.level == level)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    SystemLog.action.ilike(term),
                    SystemLog.message.ilike(term),
                    SystemLog.details.ilike(term),
                    SystemLog.user_email.ilike(term)
                )
            )

        return query.order_by(desc(SystemLog.created_at)).offset(offset).limit(limit).all()

    @staticmethod
    def get_ai_stats(
        db: Session,
        user_id: Optional[str] = None,
        is_admin: bool = False
    ) -> Dict[str, Any]:
        """Compute summary statistics for AI calls."""
        query = db.query(AILog)
        if not is_admin and user_id:
            query = query.filter(AILog.user_id == user_id)

        total = query.count()
        success = query.filter(AILog.status == "SUCCESS").count()
        errors = query.filter(AILog.status == "ERROR").count()
        fallbacks = query.filter(or_(AILog.status == "FALLBACK_RULE_BASED", AILog.status == "PARSE_ERROR")).count()

        avg_lat = query.with_entities(func.avg(AILog.latency_ms)).scalar() or 0.0

        return {
            "total_calls": total,
            "success_count": success,
            "error_count": errors,
            "fallback_count": fallbacks,
            "avg_latency_ms": round(float(avg_lat), 1)
        }

    @staticmethod
    def clear_logs(
        db: Session,
        log_type: str = "all",
        user_id: Optional[str] = None,
        is_admin: bool = False
    ) -> int:
        """Clear logs (admin can clear all; regular users only clear their own)."""
        deleted_count = 0
        if log_type in ("ai", "all"):
            q_ai = db.query(AILog)
            if not is_admin and user_id:
                q_ai = q_ai.filter(AILog.user_id == user_id)
            deleted_count += q_ai.delete(synchronize_session=False)

        if log_type in ("system", "all"):
            q_sys = db.query(SystemLog)
            if not is_admin and user_id:
                q_sys = q_sys.filter(SystemLog.user_id == user_id)
            deleted_count += q_sys.delete(synchronize_session=False)

        db.commit()
        return deleted_count
