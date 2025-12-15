# app/api/v1/auth/password.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.core.exceptions import AppError, ValidationError, NotFoundError, ConflictError
from app.core.security import decode_token, TokenDecodeError
from app.schemas.auth import (
    PasswordResetRequest,
    PasswordChangeRequest,
    PasswordChangeResponse,
    TokenData,
)
from app.schemas.common.response import MessageResponse
from app.services.common import UnitOfWork
from app.services.auth import PasswordService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_uow(session: Session = Depends(get_session)) -> UnitOfWork:
    return UnitOfWork(session)


def get_password_service(uow: UnitOfWork = Depends(get_uow)) -> PasswordService:
    return PasswordService(uow)


def _handle_service_error(exc: AppError) -> HTTPException:
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    if isinstance(exc, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )


def get_current_user_id(
    authorization: str = Header(..., description="Bearer access token"),
) -> UUID:
    """
    Extract current user's ID from Authorization: Bearer <token> header.
    Assumes JWT payload matches TokenData schema.
    """
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
        data = TokenData(**payload)
    except TokenDecodeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return data.user_id  # assumes TokenData has user_id: UUID


@router.post(
    "/password/reset",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
def request_password_reset(
    payload: PasswordResetRequest,
    service: PasswordService = Depends(get_password_service),
) -> MessageResponse:
    """
    Initiate password reset (e.g., send reset email/OTP).
    """
    try:
        # Adjust method name/signature if your PasswordService differs.
        service.request_password_reset(payload)
        return MessageResponse(message="Password reset instructions sent")
    except AppError as exc:
        raise _handle_service_error(exc)


@router.post(
    "/password/change",
    response_model=PasswordChangeResponse,
    status_code=status.HTTP_200_OK,
)
def change_password(
    payload: PasswordChangeRequest,
    user_id: UUID = Depends(get_current_user_id),
    service: PasswordService = Depends(get_password_service),
) -> PasswordChangeResponse:
    """
    Change password for the currently authenticated user.

    Expects current_password + new_password in the payload.
    """
    try:
        # Adjust method signature if your PasswordService differs.
        return service.change_password(user_id=user_id, data=payload)
    except AppError as exc:
        raise _handle_service_error(exc)