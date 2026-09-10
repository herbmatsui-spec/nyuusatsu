from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Optional

import jwt
from sqlalchemy.orm import Session

from database.models.user import User
from database.models.role import Role, UserRole
from database.models.organization import Organization
from config import AppConfig, PlanConfig


class AuthService:
    def __init__(self, session: Session, config: Optional[AppConfig] = None):
        self.session = session
        self.config = config or AppConfig()

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.session.query(User).filter(User.username == username, User.is_active == True).first()
        if not user:
            return None
        if not self._verify_password(password, user.password_hash or ""):
            return None
        return user

    def create_user(self, username: str, password: str, org_id: Optional[int] = None, email: Optional[str] = None) -> User:
        now = datetime.utcnow()
        user = User(
            username=username,
            email=email,
            password_hash=self._hash_password(password),
            org_id=org_id,
            is_active=True,
            created_at=now,
            plan=PlanConfig.FREE,
            trial_ends_at=now + timedelta(days=7),
            subscription_status="trialing",
        )
        self.session.add(user)
        self.session.flush()
        return user

    def load_user(self, user_id: str) -> Optional[User]:
        """Flask-Login user loader."""
        try:
            return self.session.query(User).filter(User.id == int(user_id)).first()
        except (ValueError, TypeError):
            return None

    def get_user_by_stripe_customer(self, customer_id: str) -> Optional[User]:
        """Find user by Stripe customer ID."""
        return self.session.query(User).filter(User.stripe_customer_id == customer_id).first()

    def create_token(self, user: User, expires_minutes: int = 60) -> str:
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
        }
        return jwt.encode(payload, "secret", algorithm="HS256")

    def get_current_user(self, token: Optional[str]) -> Optional[User]:
        if not token:
            return None
        try:
            payload = jwt.decode(token, "secret", algorithms=["HS256"])
        except jwt.PyJWTError:
            return None
        return self.session.get(User, int(payload.get("sub", 0)))

    def has_permission(self, user: User, action: str, resource: str) -> bool:
        import json as _json
        roles = (
            self.session.query(UserRole)
            .filter(UserRole.user_id == user.id)
            .all()
        )
        for ur in roles:
            role = self.session.get(Role, ur.role_id)
            if not role:
                continue
            try:
                perms = _json.loads(role.permissions_json or "[]")
            except _json.JSONDecodeError:
                continue
            target = f"{resource}:{action}"
            if target in perms or f"{resource}:*" in perms:
                return True
        return False

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        return AuthService._hash_password(password) == password_hash
