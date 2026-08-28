"""Generic repository base used by the thin per-model repositories."""
from typing import Any, Dict, List, Optional, Type

from sqlalchemy.orm import Session


class BaseRepository:
    """Minimal CRUD wrapper. Concrete repos set ``model``."""

    model: Type = None

    def __init__(self, session: Session):
        self.session = session

    def query(self):
        return self.session.query(self.model)

    def get_by_id(self, pk: Any):
        return self.session.get(self.model, pk)

    def filter_by(self, **kwargs):
        return self.session.query(self.model).filter_by(**kwargs).all()

    def first_by(self, **kwargs):
        return self.session.query(self.model).filter_by(**kwargs).first()

    def all(self) -> List:
        return self.session.query(self.model).all()

    def add(self, obj) -> None:
        self.session.add(obj)

    def save(self, obj=None) -> None:
        if obj is not None:
            self.session.add(obj)
        self.session.commit()

    def create(self, **kwargs):
        obj = self.model(**kwargs)
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def delete(self, obj) -> None:
        self.session.delete(obj)
        self.session.commit()
