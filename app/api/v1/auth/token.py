from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.token import (
    RefreshTokenRequest,
    RefreshTokenResponse,
    TokenValidationRequest,
    TokenValidationResponse,
    RevokeTokenRequest,
)
# Using TokenService for token-specific operations, or AuthenticationService.
from app.services.auth.token_service import TokenService
from app.services.auth.authentication_service import AuthenticationService

router = APIRouter(prefix="/token", tags=["auth:token"])


def get_token_service(db: Session = Depends(deps.get_db)) -> TokenService:
    return TokenService(db=db)


def get_auth_service(db: Session = Depends(deps.get_db)) -> AuthenticationService:
    return AuthenticationService(db=db)


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    summary="Refresh access token",
)
def refresh_token(
    payload: RefreshTokenRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> Any:
    """
    Get a new access token using a valid refresh token.
    """
    return service.refresh(payload=payload)


@router.post(
    "/validate",
    response_model=TokenValidationResponse,
    summary="Validate token",
)
def validate_token(
    payload: TokenValidationRequest,
    service: TokenService = Depends(get_token_service),
) -> Any:
    """
    Check if a token is valid (signature, expiration, blacklist status).
    """
    return service.validate(token=payload.token)


@router.post(
    "/revoke",
    status_code=status.HTTP_200_OK,
    summary="Revoke token",
)
def revoke_token(
    payload: RevokeTokenRequest,
    current_user=Depends(deps.get_current_user),
    service: TokenService = Depends(get_token_service),
) -> Any:
    """
    Revoke a specific token (add to blacklist).
    """
    # Assuming revocation logic in TokenService, or use TokenBlacklistService directly.
    # This might require TokenBlacklistService injection if logic is separated.
    # For now, we assume TokenService handles it or delegates.
    return service.revoke(token=payload.token, user_id=current_user.id)