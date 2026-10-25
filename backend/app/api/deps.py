from collections.abc import Generator

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import SessionLocal
from app.services.auth_service import AuthService


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_csrf_header(request: Request) -> None:
    # CSRF check: all state-changing methods require X-Rapier-Action: 1
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        header = request.headers.get("x-rapier-action")
        if header != "1":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing or invalid X-Rapier-Action header",
            )


def get_current_user_optional(
    rapier_session: str | None = Cookie(None),
    db: Session = Depends(get_db),
) -> User | None:
    if not rapier_session:
        return None
    return AuthService.get_user_by_session_token(db, rapier_session)


def get_current_user(
    rapier_session: str | None = Cookie(None),
    db: Session = Depends(get_db),
) -> User:
    if not rapier_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = AuthService.get_user_by_session_token(db, rapier_session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalid or expired",
        )
    return user
