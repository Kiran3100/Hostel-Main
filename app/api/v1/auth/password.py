from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.password import (
    PasswordChangeRequest,
    PasswordChangeResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordStrengthCheck,
    PasswordStrengthResponse,
)
from app.services.auth.password_service import PasswordService

router = APIRouter(prefix="/password", tags=["auth:password"])


def get_password_service(db: Session = Depends(deps.get_db)) -> PasswordService:
    return PasswordService(db=db)


@router.post(
    "/change",
    response_model=PasswordChangeResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password",
)
def change_password(
    payload: PasswordChangeRequest,
    current_user=Depends(deps.get_current_user),
    service: PasswordService = Depends(get_password_service),
) -> Any:
    """
    Change password for authenticated user.
    """
    return service.change_password(user_id=current_user.id, payload=payload)


@router.post(
    "/reset/request",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
)
def request_password_reset(
    payload: PasswordResetRequest,
    service: PasswordService = Depends(get_password_service),
) -> Any:
    """
    Initiate password reset flow (e.g., send reset link/email).
    """
    return service.request_reset(payload=payload)


@router.post(
    "/reset/confirm",
    status_code=status.HTTP_200_OK,
    summary="Confirm password reset",
)
def confirm_password_reset(
    payload: PasswordResetConfirm,
    service: PasswordService = Depends(get_password_service),
) -> Any:
    """
    Complete password reset using a token.
    """
    return service.confirm_reset(payload=payload)


@router.post(
    "/strength",
    response_model=PasswordStrengthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check password strength",
)
def check_password_strength(
    payload: PasswordStrengthCheck,
    service: PasswordService = Depends(get_password_service),
) -> Any:
    """
    Evaluate password strength without changing it.
    """
    return service.strength_check(payload=payload)