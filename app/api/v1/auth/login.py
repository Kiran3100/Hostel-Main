# app/api/v1/auth/login.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.core.exceptions import AppError, ValidationError, NotFoundError, ConflictError
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.common import UnitOfWork
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_uow(session: Session = Depends(get_session)) -> UnitOfWork:
    """Provide a UnitOfWork bound to the current DB session."""
    return UnitOfWork(session)


def get_auth_service(uow: UnitOfWork = Depends(get_uow)) -> AuthService:
    """Provide AuthService instance."""
    return AuthService(uow)


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


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """
    Authenticate a user using email/phone + password and return access/refresh tokens
    plus basic user info.
    """
    try:
        # Adjust method name/signature if your AuthService differs.
        return service.login(payload)
    except AppError as exc:
        raise _handle_service_error(exc)