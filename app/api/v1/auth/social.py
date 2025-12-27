from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.social_auth import (
    GoogleAuthRequest,
    FacebookAuthRequest,
    SocialAuthResponse,
    SocialAuthRequest,  # Generic
)
from app.services.auth.social_auth_service import SocialAuthService

router = APIRouter(prefix="/social", tags=["auth:social"])


def get_social_auth_service(db: Session = Depends(deps.get_db)) -> SocialAuthService:
    return SocialAuthService(db=db)


@router.post(
    "/google",
    response_model=SocialAuthResponse,
    summary="Google login",
)
def google_login(
    payload: GoogleAuthRequest,
    service: SocialAuthService = Depends(get_social_auth_service),
) -> Any:
    return service.google_login(payload=payload)


@router.post(
    "/facebook",
    response_model=SocialAuthResponse,
    summary="Facebook login",
)
def facebook_login(
    payload: FacebookAuthRequest,
    service: SocialAuthService = Depends(get_social_auth_service),
) -> Any:
    return service.facebook_login(payload=payload)


@router.post(
    "/link",
    status_code=status.HTTP_200_OK,
    summary="Link social account",
)
def link_social_account(
    payload: SocialAuthRequest,
    current_user=Depends(deps.get_current_user),
    service: SocialAuthService = Depends(get_social_auth_service),
) -> Any:
    """
    Link a social account to the currently authenticated user.
    """
    return service.link_social_account(user_id=current_user.id, payload=payload)


@router.post(
    "/unlink",
    status_code=status.HTTP_200_OK,
    summary="Unlink social account",
)
def unlink_social_account(
    payload: SocialAuthRequest,  # Usually needs provider info
    current_user=Depends(deps.get_current_user),
    service: SocialAuthService = Depends(get_social_auth_service),
) -> Any:
    return service.unlink_social_account(user_id=current_user.id, payload=payload)