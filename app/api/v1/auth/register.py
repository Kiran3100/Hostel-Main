"""
User registration and verification endpoints.

This module provides endpoints for:
- User registration/signup
- Email verification
- Phone number verification
- Resending verification codes
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.register import (
    RegisterRequest,
    RegisterResponse,
    VerifyEmailRequest,
    VerifyPhoneRequest,
    ResendVerificationRequest,
)
from app.services.auth.authentication_service import AuthenticationService
from app.services.user.user_verification_service import UserVerificationService

# Router configuration
router = APIRouter(
    prefix="/register",
    tags=["auth:register"],
    responses={
        400: {"description": "Invalid registration data"},
        409: {"description": "User already exists"},
        422: {"description": "Validation error"},
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


def get_verification_service(
    db: Session = Depends(deps.get_db)
) -> UserVerificationService:
    """
    Dependency injection for UserVerificationService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        UserVerificationService instance
    """
    return UserVerificationService(db=db)


@router.post(
    "",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with email/phone verification.",
    response_description="Newly created user data with verification instructions",
)
async def register_user(
    payload: RegisterRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> RegisterResponse:
    """
    Register a new user account.
    
    Creates a new user and initiates the verification process.
    
    Args:
        payload: Registration data including email, password, and user details
        service: Authentication service instance
        
    Returns:
        RegisterResponse containing user data and verification instructions
        
    Raises:
        HTTPException: If user already exists or registration fails
    """
    try:
        return service.register(payload=payload)
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
            detail="An error occurred during registration",
        ) from e


@router.post(
    "/verify/email",
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
    description="Verify user's email address using the provided verification code.",
    response_description="Email verification confirmation",
)
async def verify_email(
    payload: VerifyEmailRequest,
    service: UserVerificationService = Depends(get_verification_service),
) -> Dict[str, str]:
    """
    Verify email address.
    
    Args:
        payload: Email verification request containing verification code
        service: User verification service instance
        
    Returns:
        Success message confirming email verification
        
    Raises:
        HTTPException: If verification code is invalid or expired
    """
    try:
        service.verify_email(payload=payload)
        return {"message": "Email verified successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during email verification",
        ) from e


@router.post(
    "/verify/phone",
    status_code=status.HTTP_200_OK,
    summary="Verify phone number",
    description="Verify user's phone number using the provided verification code.",
    response_description="Phone verification confirmation",
)
async def verify_phone(
    payload: VerifyPhoneRequest,
    service: UserVerificationService = Depends(get_verification_service),
) -> Dict[str, str]:
    """
    Verify phone number.
    
    Args:
        payload: Phone verification request containing verification code
        service: User verification service instance
        
    Returns:
        Success message confirming phone verification
        
    Raises:
        HTTPException: If verification code is invalid or expired
    """
    try:
        service.verify_phone(payload=payload)
        return {"message": "Phone number verified successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during phone verification",
        ) from e


@router.post(
    "/verify/resend",
    status_code=status.HTTP_200_OK,
    summary="Resend verification code",
    description="Resend verification code to email or phone number.",
    response_description="Verification code resend confirmation",
)
async def resend_verification(
    payload: ResendVerificationRequest,
    service: UserVerificationService = Depends(get_verification_service),
) -> Dict[str, str]:
    """
    Resend verification code.
    
    Args:
        payload: Resend request specifying delivery method
        service: User verification service instance
        
    Returns:
        Success message confirming code has been resent
        
    Raises:
        HTTPException: If rate limit is exceeded or resend fails
    """
    try:
        service.resend_verification_code(payload=payload)
        return {"message": "Verification code has been resent"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resending verification code",
        ) from e