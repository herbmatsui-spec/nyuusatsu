from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Optional
from functools import wraps

from sqlalchemy.orm import Session
from database.models.audit_log import AuditLog


class AuditLogger:
    def __init__(self, session: Session):
        self.session = session

    def log(self, user_id: Optional[str], action: str, resource_type: Optional[str] = None, resource_id: Optional[int] = None, ip: Optional[str] = None, detail: Optional[dict] = None):
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip=ip,
            detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
        )
        self.session.add(log_entry)
        self.session.flush()


def audit_log(action: str, resource_type: Optional[str] = None):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = kwargs.get("user_id") or (args[0] if args else None)
            ip = kwargs.get("ip")
            detail = kwargs.get("detail")
            session = kwargs.get("session")
            if session:
                logger = AuditLogger(session)
                resource_id = kwargs.get("resource_id") or (args[1] if len(args) > 1 else None)
                logger.log(
                    user_id=str(user_id) if user_id else None,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip=ip,
                    detail=detail,
                )
                session.commit()
            return func(*args, **kwargs)
        return wrapper
    return decorator
