# app/api/v1/referrals/codes.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.referral import ReferralService
from app.schemas.referral.referral_code import (
    ReferralCodeGenerate,
    ReferralCodeResponse,
    CodeValidationRequest,
    CodeValidationResponse,
)
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Referrals - Codes"])


def _get_service(session: Session) -> ReferralService:
    uow = UnitOfWork(session)
    return ReferralService(uow)


@router.post("/generate", response_model=ReferralCodeResponse)
def generate_referral_code(
    payload: ReferralCodeGenerate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReferralCodeResponse:
    """
    Generate a referral code for the authenticated user.

    (Typically 1 code per active program/user combination, but up to service logic.)
    """
    service = _get_service(session)
    # Expected: generate_code(referrer_id: UUID, data: ReferralCodeGenerate) -> ReferralCodeResponse
    return service.generate_code(
        referrer_id=current_user.id,
        data=payload,
    )


@router.post("/validate", response_model=CodeValidationResponse)
def validate_referral_code(
    payload: CodeValidationRequest,
    session: Session = Depends(get_session),
) -> CodeValidationResponse:
    """
    Validate a referral code (public endpoint).

    Returns validity, associated program/benefits, and potential referrer info.
    """
    service = _get_service(session)
    # Expected: validate_code(request: CodeValidationRequest) -> CodeValidationResponse
    return service.validate_code(request=payload)