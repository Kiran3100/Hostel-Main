# app/api/v1/subscriptions/__init__.py
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
    """Minimal representation of the authenticated user for subscription APIs."""
    id: UUID
    role: UserRole


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """
    Decode JWT and return minimal CurrentUser.

    Expects payload to contain either:
      - sub (user id as string) and role
      - or user_id and user_role

    Adjust this if your TokenPayload uses different claim names.
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


# Import sub-routers and mount them.
from . import plans, subscriptions, upgrade, billing, cancellation, commission  # noqa: E402

router.include_router(plans.router, prefix="/plans")
router.include_router(subscriptions.router, prefix="/subscriptions")
router.include_router(upgrade.router, prefix="/upgrade")
router.include_router(billing.router, prefix="/billing")
router.include_router(cancellation.router, prefix="/cancellation")
router.include_router(commission.router, prefix="/commission")

__all__ = [
    "router",
    "CurrentUser",
    "get_current_user",
]