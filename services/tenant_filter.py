from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from config import AppConfig


class TenantFilter:
    def __init__(self, session: Session, user, config: Optional[AppConfig] = None):
        self.session = session
        self.user = user
        self.config = config or AppConfig()

    def apply(self, query):
        if not self.user:
            return query
        if hasattr(self.user, "org_id") and self.user.org_id:
            mapper = inspect(query.column_descriptions[0]["type"]).mapper
            if hasattr(mapper.class_, "org_id"):
                return query.filter(mapper.class_.org_id == self.user.org_id)
        return query
