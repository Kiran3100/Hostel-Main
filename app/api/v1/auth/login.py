"""
Authentication login endpoints.

This module provides endpoints for user authentication including:
- Email/password login
- Phone number login with OTP verification
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.login import (
    LoginRequest,
    LoginResponse,
    PhoneLoginRequest,
)
from app.services.auth.authentication_service import AuthenticationService

# Router configuration
router = APIRouter(
    prefix="/login",
    tags=["auth:login"],
    responses={
        401: {"description": "Invalid credentials"},
        422: {"description": "Validation error"},
        429: {"description": "Too many login attempts"},
    },
)


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
    "",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with email and password",
    description="Authenticate user using email and password credentials.",
    response_description="Successfully authenticated user with access and refresh tokens",
)
async def login(
    payload: LoginRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> LoginResponse:
    """
    Authenticate user using email and password.
    
    Args:
        payload: Login credentials containing email and password
        service: Authentication service instance
        
    Returns:
        LoginResponse containing access token, refresh token, and user data
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        return service.login(payload=payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during authentication",
        ) from e


@router.post(
    "/phone",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with phone number",
    description="Authenticate user using phone number and OTP verification.",
    response_description="Successfully authenticated user with access and refresh tokens",
)
async def phone_login(
    payload: PhoneLoginRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> LoginResponse:
    """
    Authenticate user using phone number with OTP verification.
    
    Args:
        payload: Phone login credentials containing phone number and OTP
        service: Authentication service instance
        
    Returns:
        LoginResponse containing access token, refresh token, and user data
        
    Raises:
        HTTPException: If authentication fails or OTP is invalid
    """
    try:
        return service.phone_login(payload=payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during phone authentication",
        ) from e