from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.register import (
    RegisterRequest,
    RegisterResponse,
    VerifyEmailRequest,
    VerifyPhoneRequest,
    ResendVerificationRequest,
)
# Note: Registration logic might reside in AuthenticationService or a dedicated RegistrationService.
# Based on your services, AuthenticationService seems appropriate, or UserService.
# Assuming AuthenticationService handles signup or delegates it.
from app.services.auth.authentication_service import AuthenticationService
from app.services.user.user_verification_service import UserVerificationService

router = APIRouter(prefix="/register", tags=["auth:register"])


def get_auth_service(db: Session = Depends(deps.get_db)) -> AuthenticationService:
    return AuthenticationService(db=db)


def get_verification_service(db: Session = Depends(deps.get_db)) -> UserVerificationService:
    return UserVerificationService(db=db)


@router.post(
    "",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
)
def register_user(
    payload: RegisterRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> Any:
    """
    Register a new user account.
    """
    # Assuming `register` method exists in AuthenticationService or similar.
    # If not, use UserService.create_user.
    return service.register(payload=payload)


@router.post(
    "/verify/email",
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
)
def verify_email(
    payload: VerifyEmailRequest,
    service: UserVerificationService = Depends(get_verification_service),
) -> Any:
    return service.verify_email(payload=payload)


@router.post(
    "/verify/phone",
    status_code=status.HTTP_200_OK,
    summary="Verify phone number",
)
def verify_phone(
    payload: VerifyPhoneRequest,
    service: UserVerificationService = Depends(get_verification_service),
) -> Any:
    return service.verify_phone(payload=payload)


@router.post(
    "/verify/resend",
    status_code=status.HTTP_200_OK,
    summary="Resend verification code",
)
def resend_verification(
    payload: ResendVerificationRequest,
    service: UserVerificationService = Depends(get_verification_service),
) -> Any:
    return service.resend_verification_code(payload=payload)