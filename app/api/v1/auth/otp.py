from typing import Any

from fastapi import APIRouter, Depends, status
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

router = APIRouter(prefix="/otp", tags=["auth:otp"])


def get_otp_service(db: Session = Depends(deps.get_db)) -> OTPService:
    return OTPService(db=db)


@router.post(
    "/generate",
    response_model=OTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate OTP",
)
def generate_otp(
    payload: OTPGenerateRequest,
    service: OTPService = Depends(get_otp_service),
) -> Any:
    """
    Generate and send an OTP (via email or SMS).
    """
    return service.generate(payload=payload)


@router.post(
    "/verify",
    response_model=OTPVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP",
)
def verify_otp(
    payload: OTPVerifyRequest,
    service: OTPService = Depends(get_otp_service),
) -> Any:
    """
    Verify the provided OTP code.
    """
    return service.verify(payload=payload)


@router.post(
    "/resend",
    response_model=OTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend OTP",
)
def resend_otp(
    payload: ResendOTPRequest,
    service: OTPService = Depends(get_otp_service),
) -> Any:
    """
    Resend OTP with rate limiting.
    """
    return service.resend(payload=payload)