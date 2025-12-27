"""
Password management endpoints.

This module provides endpoints for password operations including:
- Password change for authenticated users
- Password reset request and confirmation
- Password strength validation
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
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

# Router configuration
router = APIRouter(
    prefix="/password",
    tags=["auth:password"],
    responses={
        400: {"description": "Invalid password or request"},
        401: {"description": "Unauthorized - Invalid credentials"},
        404: {"description": "User not found"},
    },
)


def get_password_service(db: Session = Depends(deps.get_db)) -> PasswordService:
    """
    Dependency injection for PasswordService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        PasswordService instance
    """
    return PasswordService(db=db)


@router.post(
    "/change",
    response_model=PasswordChangeResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password",
    description="Change password for the currently authenticated user.",
    response_description="Password change confirmation",
)
async def change_password(
    payload: PasswordChangeRequest,
    current_user=Depends(deps.get_current_user),
    service: PasswordService = Depends(get_password_service),
) -> PasswordChangeResponse:
    """
    Change password for authenticated user.
    
    Requires current password verification before setting new password.
    
    Args:
        payload: Password change request containing old and new passwords
        current_user: Currently authenticated user from dependency injection
        service: Password service instance
        
    Returns:
        PasswordChangeResponse confirming password update
        
    Raises:
        HTTPException: If current password is incorrect or new password is invalid
    """
    try:
        return service.change_password(user_id=current_user.id, payload=payload)
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
            detail="An error occurred while changing password",
        ) from e


@router.post(
    "/reset/request",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Initiate password reset flow by sending reset link to user's email.",
    response_description="Password reset request confirmation",
)
async def request_password_reset(
    payload: PasswordResetRequest,
    service: PasswordService = Depends(get_password_service),
) -> Dict[str, str]:
    """
    Initiate password reset flow.
    
    Sends a password reset link/token to the user's email address.
    
    Args:
        payload: Password reset request containing email or identifier
        service: Password service instance
        
    Returns:
        Success message (always returns success for security reasons)
        
    Note:
        For security, this endpoint returns success even if user doesn't exist
    """
    try:
        service.request_reset(payload=payload)
        return {
            "message": "If the email exists, a password reset link has been sent",
        }
    except Exception as e:
        # Log the error but return generic success message for security
        # logger.error(f"Password reset request error: {str(e)}")
        return {
            "message": "If the email exists, a password reset link has been sent",
        }


@router.post(
    "/reset/confirm",
    status_code=status.HTTP_200_OK,
    summary="Confirm password reset",
    description="Complete password reset using the provided reset token.",
    response_description="Password reset confirmation",
)
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    service: PasswordService = Depends(get_password_service),
) -> Dict[str, str]:
    """
    Complete password reset using a token.
    
    Args:
        payload: Password reset confirmation containing token and new password
        service: Password service instance
        
    Returns:
        Success message confirming password has been reset
        
    Raises:
        HTTPException: If token is invalid, expired, or password is weak
    """
    try:
        service.confirm_reset(payload=payload)
        return {"message": "Password has been successfully reset"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting password",
        ) from e


@router.post(
    "/strength",
    response_model=PasswordStrengthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check password strength",
    description="Evaluate password strength without storing or changing it.",
    response_description="Password strength analysis",
)
async def check_password_strength(
    payload: PasswordStrengthCheck,
    service: PasswordService = Depends(get_password_service),
) -> PasswordStrengthResponse:
    """
    Evaluate password strength.
    
    Analyzes the password against various criteria without storing it.
    
    Args:
        payload: Password strength check request containing password to evaluate
        service: Password service instance
        
    Returns:
        PasswordStrengthResponse with strength score and recommendations
        
    Raises:
        HTTPException: If password evaluation fails
    """
    try:
        return service.strength_check(payload=payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while checking password strength",
        ) from e