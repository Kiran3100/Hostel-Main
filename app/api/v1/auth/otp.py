# app/api/v1/auth/otp.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.core.exceptions import AppError, ValidationError, NotFoundError
from app.schemas.auth import (
    OTPGenerateRequest,
    OTPVerifyRequest,
    OTPResponse,
    OTPVerifyResponse,
)
from app.services.common import UnitOfWork
from app.services.auth import OTPService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_uow(session: Session = Depends(get_session)) -> UnitOfWork:
    return UnitOfWork(session)


def get_otp_service(uow: UnitOfWork = Depends(get_uow)) -> OTPService:
    return OTPService(uow)


def _handle_service_error(exc: AppError) -> HTTPException:
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    if isinstance(exc, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )


@router.post("/otp/send", response_model=OTPResponse, status_code=status.HTTP_200_OK)
def send_otp(
    payload: OTPGenerateRequest,
    service: OTPService = Depends(get_otp_service),
) -> OTPResponse:
    """
    Generate and send an OTP for a given identifier (email/phone) and purpose.
    """
    try:
        # Adjust method name/signature if your OTPService differs.
        return service.generate_otp(payload)
    except AppError as exc:
        raise _handle_service_error(exc)


@router.post("/otp/verify", response_model=OTPVerifyResponse, status_code=status.HTTP_200_OK)
def verify_otp(
    payload: OTPVerifyRequest,
    service: OTPService = Depends(get_otp_service),
) -> OTPVerifyResponse:
    """
    Verify a previously sent OTP.
    """
    try:
        # Adjust method name/signature if your OTPService differs.
        return service.verify_otp(payload)
    except AppError as exc:
        raise _handle_service_error(exc)