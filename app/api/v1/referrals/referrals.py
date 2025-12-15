# app/api/v1/referrals/referrals.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.referral import ReferralService
from app.schemas.referral.referral_base import ReferralCreate
from app.schemas.referral.referral_response import ReferralResponse, ReferralStats
from . import CurrentUser, get_current_user, get_current_admin

router = APIRouter(tags=["Referrals - Referrals"])


def _get_service(session: Session) -> ReferralService:
    uow = UnitOfWork(session)
    return ReferralService(uow)


@router.post("/", response_model=ReferralResponse)
def create_referral(
    payload: ReferralCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReferralResponse:
    """
    Create a referral record for the current user as referrer.
    """
    service = _get_service(session)
    # Expected: create_referral(referrer_id: UUID, data: ReferralCreate) -> ReferralResponse
    return service.create_referral(
        referrer_id=current_user.id,
        data=payload,
    )


@router.get("/me", response_model=ReferralStats)
def get_my_referral_stats(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReferralStats:
    """
    Get aggregated referral statistics for the authenticated user.
    """
    service = _get_service(session)
    # Expected: get_stats_for_referrer(referrer_id: UUID) -> ReferralStats
    return service.get_stats_for_referrer(referrer_id=current_user.id)


@router.get("/me/list", response_model=List[ReferralResponse])
def list_my_referrals(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[ReferralResponse]:
    """
    List all referrals created by the authenticated user.
    """
    service = _get_service(session)
    # Expected: list_referrals_for_referrer(referrer_id: UUID) -> list[ReferralResponse]
    return service.list_referrals_for_referrer(referrer_id=current_user.id)


@router.get("/{referral_id}", response_model=ReferralResponse)
def get_referral(
    referral_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReferralResponse:
    """
    Get a single referral record by ID.

    (Visible to admin or the referrer themselves.)
    """
    service = _get_service(session)
    # Expected: get_referral(referral_id: UUID, requester_id: UUID, requester_role: UserRole) -> ReferralResponse
    return service.get_referral(
        referral_id=referral_id,
        requester_id=current_user.id,
        requester_role=current_user.role,
    )


@router.get("/programs/{program_id}", response_model=List[ReferralResponse])
def list_referrals_for_program(
    program_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> List[ReferralResponse]:
    """
    Admin endpoint: list referrals under a given program.
    """
    service = _get_service(session)
    # Expected: list_referrals_for_program(program_id: UUID) -> list[ReferralResponse]
    return service.list_referrals_for_program(program_id=program_id)