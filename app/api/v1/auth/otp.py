"""
One-Time Password (OTP) endpoints.

This module provides endpoints for OTP operations including:
- OTP generation and delivery (email/SMS)
- OTP verification
- OTP resend with rate limiting
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.otp import (
    OTPGenerateRequest,
    OTPResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
    ResendOTPRequest,
)
from app.services.auth.otp_service import OTPService

# Router configuration
router = APIRouter(
    prefix="/otp",
    tags=["auth:otp"],
    responses={
        400: {"description": "Invalid OTP or request"},
        429: {"description": "Too many OTP requests - rate limit exceeded"},
    },
)


def get_otp_service(db: Session = Depends(deps.get_db)) -> OTPService:
    """
    Dependency injection for OTPService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        OTPService instance
    """
    return OTPService(db=db)


@router.post(
    "/generate",
    response_model=OTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate OTP",
    description="Generate and send an OTP code via email or SMS.",
    response_description="OTP generation confirmation with delivery details",
)
async def generate_otp(
    payload: OTPGenerateRequest,
    service: OTPService = Depends(get_otp_service),
) -> OTPResponse:
    """
    Generate and send an OTP.
    
    The OTP can be delivered via email or SMS based on the request payload.
    
    Args:
        payload: OTP generation request containing delivery method and recipient
        service: OTP service instance
        
    Returns:
        OTPResponse confirming OTP generation and delivery
        
    Raises:
        HTTPException: If OTP generation fails or rate limit is exceeded
    """
    try:
        return service.generate(payload=payload)
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
            detail="An error occurred while generating OTP",
        ) from e


@router.post(
    "/verify",
    response_model=OTPVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP",
    description="Verify the provided OTP code against the stored value.",
    response_description="OTP verification result",
)
async def verify_otp(
    payload: OTPVerifyRequest,
    service: OTPService = Depends(get_otp_service),
) -> OTPVerifyResponse:
    """
    Verify the provided OTP code.
    
    Args:
        payload: OTP verification request containing code and identifier
        service: OTP service instance
        
    Returns:
        OTPVerifyResponse indicating verification success or failure
        
    Raises:
        HTTPException: If OTP is invalid, expired, or verification fails
    """
    try:
        return service.verify(payload=payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while verifying OTP",
        ) from e


@router.post(
    "/resend",
    response_model=OTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend OTP",
    description="Resend OTP with rate limiting protection.",
    response_description="OTP resend confirmation",
)
async def resend_otp(
    payload: ResendOTPRequest,
    service: OTPService = Depends(get_otp_service),
) -> OTPResponse:
    """
    Resend OTP with rate limiting.
    
    Args:
        payload: Resend request containing identifier and delivery method
        service: OTP service instance
        
    Returns:
        OTPResponse confirming OTP has been resent
        
    Raises:
        HTTPException: If rate limit is exceeded or resend fails
    """
    try:
        return service.resend(payload=payload)
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
            detail="An error occurred while resending OTP",
        ) from e