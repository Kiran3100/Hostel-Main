# app/api/deps.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from uuid import UUID

from app.core import get_session
from app.core.security import decode_token, TokenDecodeError
from app.models import user
from app.schemas.common.enums import UserRole
from app.services.common.unit_of_work import UnitOfWork
from app.services.auth import (
    AuthService,
    OTPService,
    PasswordService,
    RegistrationService,
    SocialAuthService,
)
from app.services.announcement import (
    AnnouncementDeliveryService,
    AnnouncementTrackingService,
)
from app.services.file import (
    FileService,
    ImageService,
    DocumentService,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@dataclass
class CurrentUser:
    """Minimal authenticated user representation used by shared deps."""
    id: UUID
    role: UserRole


def _decode_token_to_current_user(token: str) -> CurrentUser:
    try:
        payload: dict[str, Any] = decode_token(token)
    except TokenDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc

    user_id_raw = payload.get("sub") or payload.get("user_id")
    role_raw = payload.get("role") or payload.get("user_role")

    if not user_id_raw or not role_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = UUID(str(user_id_raw))
        role = UserRole(str(role_raw))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        ) from exc

    return CurrentUser(id=user_id, role=role)


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """
    Decode JWT and return a minimal `CurrentUser` (id, role).

    Used by auth/password and other generic endpoints that only need
    the user id / role, not the full ORM entity.
    """
    return _decode_token_to_current_user(token)


def get_current_active_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    """
    Return the full `User` ORM object for the authenticated user.

    Ensures the user exists and is active. Used where we need relationships
    such as `admin_profile` (e.g. multi-hostel admin dashboard).
    """
    current = _decode_token_to_current_user(token)
    user = session.get(User, current.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return user


def get_uow(session: Session = Depends(get_session)) -> UnitOfWork:
    """
    Dependency that provides a UnitOfWork bound to the current DB session.
    """
    return UnitOfWork(session)


# ---------------------- Auth services ----------------------------------------


def get_auth_service(uow: UnitOfWork = Depends(get_uow)) -> AuthService:
    """Provide AuthService with UnitOfWork."""
    return AuthService(uow)


def get_otp_service(uow: UnitOfWork = Depends(get_uow)) -> OTPService:
    """Provide OTPService (backed by a store configured in the service layer)."""
    return OTPService(uow)


def get_password_service(uow: UnitOfWork = Depends(get_uow)) -> PasswordService:
    """Provide PasswordService."""
    return PasswordService(uow)


def get_registration_service(uow: UnitOfWork = Depends(get_uow)) -> RegistrationService:
    """Provide RegistrationService."""
    return RegistrationService(uow)


def get_social_auth_service(uow: UnitOfWork = Depends(get_uow)) -> SocialAuthService:
    """Provide SocialAuthService."""
    return SocialAuthService(uow)


# ---------------------- Announcement services --------------------------------


def get_announcement_delivery_service(
    uow: UnitOfWork = Depends(get_uow),
) -> AnnouncementDeliveryService:
    """Provide AnnouncementDeliveryService."""
    return AnnouncementDeliveryService(uow)


def get_announcement_tracking_service(
    uow: UnitOfWork = Depends(get_uow),
) -> AnnouncementTrackingService:
    """Provide AnnouncementTrackingService."""
    return AnnouncementTrackingService(uow)


# ---------------------- File / image / document services ---------------------


def get_file_service(uow: UnitOfWork = Depends(get_uow)) -> FileService:
    """Provide FileService."""
    return FileService(uow)


def get_image_service(uow: UnitOfWork = Depends(get_uow)) -> ImageService:
    """Provide ImageService."""
    return ImageService(uow)


def get_document_service(uow: UnitOfWork = Depends(get_uow)) -> DocumentService:
    """Provide DocumentService."""
    return DocumentService(uow)