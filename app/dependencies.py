# app/dependencies.py
from __future__ import annotations

from typing import Annotated, Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from uuid import UUID

from app.config import settings
from app.core1.database import SessionLocal
from app.core1.security import JWTSettings, decode_token
from app.schemas.common.enums import UserRole
from app.services.common import UnitOfWork
from app.services.auth import AuthService, RegistrationService, PasswordService
from app.services.booking import BookingService
from app.services.complaint import ComplaintService
from app.services.attendance import AttendanceService
from app.services.announcement import AnnouncementService


# OAuth2 scheme for Bearer tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ------------------------------------------------------------------ #
# DB / UnitOfWork
# ------------------------------------------------------------------ #
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a SQLAlchemy Session bound to SessionLocal.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_factory():
    """
    Provide a session factory for services that expect Callable[[], Session].
    """
    return SessionLocal


def get_uow() -> UnitOfWork:
    """
    Provide a UnitOfWork instance. Typically used only inside routers that
    want to work directly with repositories instead of services.
    """
    return UnitOfWork(get_session_factory())


def get_jwt_settings() -> JWTSettings:
    """
    Provide JWTSettings derived from application Settings.
    """
    return settings.jwt_settings


# ------------------------------------------------------------------ #
# Current user
# ------------------------------------------------------------------ #
class CurrentUser:
    """
    Lightweight representation of the authenticated user extracted from JWT.
    """

    def __init__(self, user_id: UUID, role: UserRole, email: str | None = None):
        self.id = user_id
        self.role = role
        self.email = email or ""


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    jwt_settings: JWTSettings = Depends(get_jwt_settings),
) -> CurrentUser:
    """
    Decode JWT access token and return a CurrentUser instance.

    Raises 401 on invalid or expired token.
    """
    try:
        payload = decode_token(token, jwt_settings)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        )

    user_id_str = payload.get("user_id") or payload.get("sub")
    role_str = payload.get("role")
    email = payload.get("email")

    if not user_id_str or not role_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = UUID(user_id_str)
        role = UserRole(role_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    return CurrentUser(user_id=user_id, role=role, email=email)


# ------------------------------------------------------------------ #
# Service factories
# ------------------------------------------------------------------ #
def get_auth_service(
    session_factory=Depends(get_session_factory),
    jwt_settings: JWTSettings = Depends(get_jwt_settings),
) -> AuthService:
    """
    Provide an AuthService instance with configured JWTSettings.

    UserActivityService can be injected later if/when implemented.
    """
    return AuthService(
        session_factory=session_factory,
        jwt_settings=jwt_settings,
        user_activity_service=None,
    )


def get_registration_service(
    session_factory=Depends(get_session_factory),
) -> RegistrationService:
    return RegistrationService(session_factory=session_factory)


def get_password_service(
    session_factory=Depends(get_session_factory),
) -> PasswordService:
    return PasswordService(
        session_factory=session_factory,
        user_activity_service=None,
    )


def get_booking_service(
    session_factory=Depends(get_session_factory),
) -> BookingService:
    return BookingService(session_factory=session_factory)


def get_complaint_service(
    session_factory=Depends(get_session_factory),
) -> ComplaintService:
    return ComplaintService(session_factory=session_factory)


def get_attendance_service(
    session_factory=Depends(get_session_factory),
) -> AttendanceService:
    return AttendanceService(session_factory=session_factory)


def get_announcement_service(
    session_factory=Depends(get_session_factory),
) -> AnnouncementService:
    return AnnouncementService(session_factory=session_factory)