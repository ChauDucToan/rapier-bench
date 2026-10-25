import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import argon2
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Session as DbSession
from app.db.models import User

# Argon2id per ARCHITECTURE §9.1: time_cost=2, memory_cost=65536 (64 MiB), parallelism=1
hasher = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    type=argon2.Type.ID,
)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return hasher.verify(hashed, password)
    except (VerifyMismatchError, Exception):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return db.scalar(stmt)

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return db.scalar(stmt)

    @staticmethod
    def register_user(db: Session, username: str, email: str, password: str) -> User:
        if AuthService.get_user_by_username(db, username):
            raise ValueError("Username already taken")
        if AuthService.get_user_by_email(db, email):
            raise ValueError("Email already registered")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            created_at=utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User | None:
        user = AuthService.get_user_by_email(db, email)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def create_session(db: Session, user_id: int) -> tuple[DbSession, str]:
        raw_token = secrets.token_urlsafe(32)
        hashed_id = hash_session_token(raw_token)
        now = utcnow()
        expires_at = now + timedelta(days=7)

        session = DbSession(
            id=hashed_id,
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session, raw_token

    @staticmethod
    def get_user_by_session_token(db: Session, raw_token: str) -> User | None:
        if not raw_token:
            return None
        hashed_id = hash_session_token(raw_token)
        stmt = select(DbSession).where(DbSession.id == hashed_id)
        session = db.scalar(stmt)
        if not session:
            return None

        # Expiry check
        if session.expires_at < utcnow():
            db.delete(session)
            db.commit()
            return None

        return session.user

    @staticmethod
    def delete_session(db: Session, raw_token: str) -> bool:
        if not raw_token:
            return False
        hashed_id = hash_session_token(raw_token)
        stmt = select(DbSession).where(DbSession.id == hashed_id)
        session = db.scalar(stmt)
        if session:
            db.delete(session)
            db.commit()
            return True
        return False
