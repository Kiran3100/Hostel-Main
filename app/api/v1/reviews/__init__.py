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
    """Minimal representation of the authenticated user for review APIs."""
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


def get_current_staff(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """
    Ensure the authenticated user is staff (ADMIN or SUPERVISOR) for moderation/owner actions.
    """
    if current_user.role not in {UserRole.ADMIN, UserRole.SUPERVISOR}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins or supervisors can access this endpoint",
        )
    return current_user


# Import sub-routers and mount them under /reviews in the main API router.
from . import reviews, submission, moderation, voting, response, analytics  # noqa: E402

router.include_router(reviews.router)
router.include_router(submission.router, prefix="/submission")
router.include_router(moderation.router, prefix="/moderation")
router.include_router(voting.router, prefix="/voting")
router.include_router(response.router, prefix="/response")
router.include_router(analytics.router, prefix="/analytics")

__all__ = [
    "router",
    "CurrentUser",
    "get_current_user",
    "get_current_staff",
]