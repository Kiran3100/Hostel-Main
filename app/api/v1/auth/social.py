# app/api/v1/auth/social.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.core.exceptions import AppError, ValidationError, ConflictError
from app.schemas.auth import (
    GoogleAuthRequest,
    FacebookAuthRequest,
    SocialAuthResponse,
)
from app.services.common import UnitOfWork
from app.services.auth import SocialAuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_uow(session: Session = Depends(get_session)) -> UnitOfWork:
    return UnitOfWork(session)


def get_social_auth_service(uow: UnitOfWork = Depends(get_uow)) -> SocialAuthService:
    return SocialAuthService(uow)


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
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )


@router.post("/google", response_model=SocialAuthResponse)
def google_login(
    payload: GoogleAuthRequest,
    service: SocialAuthService = Depends(get_social_auth_service),
) -> SocialAuthResponse:
    """
    Authenticate via Google OAuth.

    Expects an ID token or authorization code, depending on your chosen flow.
    """
    try:
        # Adjust method name/signature if your SocialAuthService differs.
        return service.authenticate_google(payload)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google social login not configured",
        )
    except AppError as exc:
        raise _handle_service_error(exc)


@router.post("/facebook", response_model=SocialAuthResponse)
def facebook_login(
    payload: FacebookAuthRequest,
    service: SocialAuthService = Depends(get_social_auth_service),
) -> SocialAuthResponse:
    """
    Authenticate via Facebook OAuth.
    """
    try:
        # Adjust method name/signature if your SocialAuthService differs.
        return service.authenticate_facebook(payload)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Facebook social login not configured",
        )
    except AppError as exc:
        raise _handle_service_error(exc)