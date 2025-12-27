"""
Token management endpoints.

This module provides endpoints for JWT token operations including:
- Token refresh
- Token validation
- Token revocation
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.token import (
    RefreshTokenRequest,
    RefreshTokenResponse,
    TokenValidationRequest,
    TokenValidationResponse,
    RevokeTokenRequest,
)
from app.services.auth.token_service import TokenService
from app.services.auth.authentication_service import AuthenticationService

# Router configuration
router = APIRouter(
    prefix="/token",
    tags=["auth:token"],
    responses={
        401: {"description": "Invalid or expired token"},
        403: {"description": "Token has been revoked"},
    },
)


def get_token_service(db: Session = Depends(deps.get_db)) -> TokenService:
    """
    Dependency injection for TokenService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        TokenService instance
    """
    return TokenService(db=db)


def get_auth_service(db: Session = Depends(deps.get_db)) -> AuthenticationService:
    """
    Dependency injection for AuthenticationService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        AuthenticationService instance
    """
    return AuthenticationService(db=db)


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Generate a new access token using a valid refresh token.",
    response_description="New access token and optionally new refresh token",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> RefreshTokenResponse:
    """
    Get a new access token using a valid refresh token.
    
    Args:
        payload: Refresh token request containing the refresh token
        service: Authentication service instance
        
    Returns:
        RefreshTokenResponse with new access token and optional refresh token
        
    Raises:
        HTTPException: If refresh token is invalid, expired, or revoked
    """
    try:
        return service.refresh(payload=payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while refreshing token",
        ) from e


@router.post(
    "/validate",
    response_model=TokenValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate token",
    description="Validate token signature, expiration, and blacklist status.",
    response_description="Token validation result with decoded payload",
)
async def validate_token(
    payload: TokenValidationRequest,
    service: TokenService = Depends(get_token_service),
) -> TokenValidationResponse:
    """
    Check if a token is valid.
    
    Validates token signature, expiration time, and checks if it's blacklisted.
    
    Args:
        payload: Token validation request containing the token to validate
        service: Token service instance
        
    Returns:
        TokenValidationResponse with validation status and token details
        
    Raises:
        HTTPException: If validation process fails
    """
    try:
        return service.validate(token=payload.token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while validating token",
        ) from e


@router.post(
    "/revoke",
    status_code=status.HTTP_200_OK,
    summary="Revoke token",
    description="Add a token to the blacklist to prevent further use.",
    response_description="Token revocation confirmation",
)
async def revoke_token(
    payload: RevokeTokenRequest,
    current_user=Depends(deps.get_current_user),
    service: TokenService = Depends(get_token_service),
) -> Dict[str, str]:
    """
    Revoke a specific token.
    
    Adds the token to the blacklist to prevent further use.
    
    Args:
        payload: Token revocation request containing the token to revoke
        current_user: Currently authenticated user from dependency injection
        service: Token service instance
        
    Returns:
        Success message confirming token has been revoked
        
    Raises:
        HTTPException: If token revocation fails
    """
    try:
        service.revoke(token=payload.token, user_id=current_user.id)
        return {"message": "Token has been successfully revoked"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while revoking token",
        ) from e