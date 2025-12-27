"""
Social authentication endpoints.

This module provides endpoints for social media authentication including:
- Google OAuth login
- Facebook OAuth login
- Linking social accounts to existing users
- Unlinking social accounts
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.social_auth import (
    GoogleAuthRequest,
    FacebookAuthRequest,
    SocialAuthResponse,
    SocialAuthRequest,
)
from app.services.auth.social_auth_service import SocialAuthService

# Router configuration
router = APIRouter(
    prefix="/social",
    tags=["auth:social"],
    responses={
        400: {"description": "Invalid social auth token"},
        401: {"description": "Social authentication failed"},
        409: {"description": "Social account already linked"},
    },
)


def get_social_auth_service(db: Session = Depends(deps.get_db)) -> SocialAuthService:
    """
    Dependency injection for SocialAuthService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        SocialAuthService instance
    """
    return SocialAuthService(db=db)


@router.post(
    "/google",
    response_model=SocialAuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Google OAuth login",
    description="Authenticate or register user using Google OAuth credentials.",
    response_description="Authentication tokens and user data",
)
async def google_login(
    payload: GoogleAuthRequest,
    service: SocialAuthService = Depends(get_social_auth_service),
) -> SocialAuthResponse:
    """
    Authenticate using Google OAuth.
    
    Creates a new user if not exists, or logs in existing user.
    
    Args:
        payload: Google authentication request containing OAuth token
        service: Social auth service instance
        
    Returns:
        SocialAuthResponse with access token, refresh token, and user data
        
    Raises:
        HTTPException: If Google token is invalid or authentication fails
    """
    try:
        return service.google_login(payload=payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during Google authentication",
        ) from e


@router.post(
    "/facebook",
    response_model=SocialAuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Facebook OAuth login",
    description="Authenticate or register user using Facebook OAuth credentials.",
    response_description="Authentication tokens and user data",
)
async def facebook_login(
    payload: FacebookAuthRequest,
    service: SocialAuthService = Depends(get_social_auth_service),
) -> SocialAuthResponse:
    """
    Authenticate using Facebook OAuth.
    
    Creates a new user if not exists, or logs in existing user.
    
    Args:
        payload: Facebook authentication request containing OAuth token
        service: Social auth service instance
        
    Returns:
        SocialAuthResponse with access token, refresh token, and user data
        
    Raises:
        HTTPException: If Facebook token is invalid or authentication fails
    """
    try:
        return service.facebook_login(payload=payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during Facebook authentication",
        ) from e


@router.post(
    "/link",
    status_code=status.HTTP_200_OK,
    summary="Link social account",
    description="Link a social media account to the currently authenticated user.",
    response_description="Social account linking confirmation",
)
async def link_social_account(
    payload: SocialAuthRequest,
    current_user=Depends(deps.get_current_user),
    service: SocialAuthService = Depends(get_social_auth_service),
) -> Dict[str, str]:
    """
    Link a social account to the currently authenticated user.
    
    Args:
        payload: Social auth request containing provider and token
        current_user: Currently authenticated user from dependency injection
        service: Social auth service instance
        
    Returns:
        Success message confirming account has been linked
        
    Raises:
        HTTPException: If account is already linked or linking fails
    """
    try:
        service.link_social_account(user_id=current_user.id, payload=payload)
        return {
            "message": f"{payload.provider.capitalize()} account linked successfully"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while linking social account",
        ) from e


@router.post(
    "/unlink",
    status_code=status.HTTP_200_OK,
    summary="Unlink social account",
    description="Remove the link between a social account and the current user.",
    response_description="Social account unlinking confirmation",
)
async def unlink_social_account(
    payload: SocialAuthRequest,
    current_user=Depends(deps.get_current_user),
    service: SocialAuthService = Depends(get_social_auth_service),
) -> Dict[str, str]:
    """
    Unlink a social account from the current user.
    
    Args:
        payload: Social auth request containing provider information
        current_user: Currently authenticated user from dependency injection
        service: Social auth service instance
        
    Returns:
        Success message confirming account has been unlinked
        
    Raises:
        HTTPException: If account is not linked or unlinking fails
    """
    try:
        service.unlink_social_account(user_id=current_user.id, payload=payload)
        return {
            "message": f"{payload.provider.capitalize()} account unlinked successfully"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while unlinking social account",
        ) from e