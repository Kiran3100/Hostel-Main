# app/api/v1/auth/token.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.core.exceptions import AppError, ValidationError
from app.schemas.auth import RefreshTokenRequest, RefreshTokenResponse
from app.services.common import UnitOfWork
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_uow(session: Session = Depends(get_session)) -> UnitOfWork:
    return UnitOfWork(session)


def get_auth_service(uow: UnitOfWork = Depends(get_uow)) -> AuthService:
    return AuthService(uow)


def _handle_service_error(exc: AppError) -> HTTPException:
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )


@router.post("/token/refresh", response_model=RefreshTokenResponse)
def refresh_token(
    payload: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> RefreshTokenResponse:
    """
    Exchange a valid refresh token for a new access (and optionally refresh) token.
    """
    try:
        # Adjust method name/signature if your AuthService differs.
        return service.refresh_token(payload)
    except AppError as exc:
        raise _handle_service_error(exc)