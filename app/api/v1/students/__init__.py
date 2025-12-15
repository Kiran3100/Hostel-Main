# app/api/v1/students/__init__.py
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_token, TokenDecodeError
from app.schemas.common.enums import UserRole

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@dataclass
class CurrentUser:
    """Minimal representation of the authenticated user."""
    id: UUID
    role: UserRole


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """
    Decode JWT and return minimal CurrentUser.

    Expects payload to contain either:
      - sub (user id as string) and role
      - or user_id and user_role
    """
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


def get_current_student(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Ensure the authenticated user is a STUDENT."""
    if current_user.role is not UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )
    return current_user


# Import sub-routers and mount them under /students in the main API router.
from . import students, profile, dashboard, room_history, finance, search  # noqa: E402

# Admin/student management endpoints
router.include_router(students.router)
# Self-profile for current student
router.include_router(profile.router, prefix="/profile")
# Self dashboard
router.include_router(dashboard.router, prefix="/dashboard")
# Room/bed history
router.include_router(room_history.router, prefix="/room-history")
# Finance
router.include_router(finance.router, prefix="/finance")
# Search
router.include_router(search.router, prefix="/search")

__all__ = [
    "router",
    "CurrentUser",
    "get_current_user",
    "get_current_student",
]