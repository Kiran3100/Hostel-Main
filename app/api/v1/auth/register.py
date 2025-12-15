# app/api/v1/auth/register.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.core.exceptions import AppError, ValidationError, NotFoundError, ConflictError
from app.schemas.auth import RegisterRequest, RegisterResponse
from app.services.common import UnitOfWork
from app.services.auth import RegistrationService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_uow(session: Session = Depends(get_session)) -> UnitOfWork:
    return UnitOfWork(session)


def get_registration_service(uow: UnitOfWork = Depends(get_uow)) -> RegistrationService:
    return RegistrationService(uow)


def _handle_service_error(exc: AppError) -> HTTPException:
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(exc, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    service: RegistrationService = Depends(get_registration_service),
) -> RegisterResponse:
    """
    Self-service registration endpoint (typically VISITOR role).
    Creates core user and visitor profile.
    """
    try:
        # Adjust method name/signature if your RegistrationService differs.
        return service.register(payload)
    except AppError as exc:
        raise _handle_service_error(exc)