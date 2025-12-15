# app/api/v1/supervisors/__init__.py
from __future__ import annotations

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
      - sub (user id) and role
      - or user_id and user_role

    Adjust this to match your actual TokenPayload.
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


def get_current_supervisor(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Ensure the authenticated user is a SUPERVISOR."""
    if current_user.role is not UserRole.SUPERVISOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only supervisors can access this endpoint",
        )
    return current_user


# Import sub-routers and mount them under /supervisors in the main API router.
from . import supervisors, dashboard, assignments, permissions, performance, activity  # noqa: E402

# CRUD / listing for supervisors
router.include_router(supervisors.router)
# Self dashboard
router.include_router(dashboard.router, prefix="/dashboard")
# Hostel assignments
router.include_router(assignments.router, prefix="/assignments")
# Permissions management
router.include_router(permissions.router, prefix="/permissions")
# Performance reports
router.include_router(performance.router, prefix="/performance")
# Activity logs
router.include_router(activity.router, prefix="/activity")

__all__ = [
    "router",
    "CurrentUser",
    "get_current_user",
    "get_current_supervisor",
]