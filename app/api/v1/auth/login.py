from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.login import (
    LoginRequest,
    LoginResponse,
    PhoneLoginRequest,
)
from app.services.auth.authentication_service import AuthenticationService

router = APIRouter(prefix="/login", tags=["auth:login"])


def get_auth_service(db: Session = Depends(deps.get_db)) -> AuthenticationService:
    return AuthenticationService(db=db)


@router.post(
    "",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with email and password",
)
def login(
    payload: LoginRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> Any:
    """
    Authenticate user using email and password.
    """
    return service.login(payload=payload)


@router.post(
    "/phone",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with phone number",
)
def phone_login(
    payload: PhoneLoginRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> Any:
    """
    Authenticate user using phone number (often combined with OTP verification logic inside service).
    """
    return service.phone_login(payload=payload)