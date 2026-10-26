from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf_header
from app.config import settings
from app.db.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf_header)],
)
def register(
    req: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.register_user(
            db=db,
            username=req.username,
            email=req.email,
            password=req.password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    # F1: registration completes authentication. The frontend treats the
    # returned user as signed-in, so a server-side session cookie must exist;
    # otherwise every protected action after signup would 401.
    _session, raw_token = AuthService.create_session(db=db, user_id=user.id)
    response.set_cookie(
        key="rapier_session",
        value=raw_token,
        max_age=604800,  # 7 days
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.SECURE_COOKIES,
    )
    return user


@router.post(
    "/login",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_csrf_header)],
)
def login(
    req: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = AuthService.authenticate_user(db=db, email=req.email, password=req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    _session, raw_token = AuthService.create_session(db=db, user_id=user.id)
    response.set_cookie(
        key="rapier_session",
        value=raw_token,
        max_age=604800,  # 7 days
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.SECURE_COOKIES,
    )
    return user


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_csrf_header)],
)
def logout(
    response: Response,
    _current_user: User = Depends(get_current_user),
    rapier_session: str | None = Cookie(None),
    db: Session = Depends(get_db),
):
    if rapier_session:
        AuthService.delete_session(db=db, raw_token=rapier_session)
    response.delete_cookie(key="rapier_session", path="/")
    return {"status": "logged_out"}


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user
