# app/api/v1/referrals/rewards.py
from datetime import date as Date
from typing import Optional, List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.referral import ReferralRewardService
from app.schemas.referral.referral_rewards import (
    RewardConfig,
    RewardTracking,
    PayoutRequest,
    PayoutRequestResponse,
)
from . import CurrentUser, get_current_user, get_current_admin

router = APIRouter(tags=["Referrals - Rewards"])


def _get_service(session: Session) -> ReferralRewardService:
    uow = UnitOfWork(session)
    return ReferralRewardService(uow)


@router.get("/config", response_model=RewardConfig)
def get_reward_config(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> RewardConfig:
    """
    Get global referral reward configuration (admin-only).
    """
    service = _get_service(session)
    # Expected: get_config() -> RewardConfig
    return service.get_config()


@router.put("/config", response_model=RewardConfig)
def update_reward_config(
    payload: RewardConfig,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> RewardConfig:
    """
    Update global referral reward configuration (admin-only).
    """
    service = _get_service(session)
    # Expected: update_config(data: RewardConfig) -> RewardConfig
    return service.update_config(data=payload)


@router.get("/me/tracking", response_model=RewardTracking)
def get_my_reward_tracking(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> RewardTracking:
    """
    Get referral rewards tracking for the authenticated user (earned/paid/pending).
    """
    service = _get_service(session)
    # Expected: get_tracking_for_user(user_id: UUID) -> RewardTracking
    return service.get_tracking_for_user(user_id=current_user.id)


@router.post("/payouts", response_model=PayoutRequestResponse, status_code=status.HTTP_201_CREATED)
def request_payout(
    payload: PayoutRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PayoutRequestResponse:
    """
    Create a payout request for the authenticated user.

    Enforces minimum payout amounts via RewardConfig.
    """
    service = _get_service(session)
    # Expected: create_payout_request(user_id: UUID, data: PayoutRequest) -> PayoutRequestResponse
    return service.create_payout_request(
        user_id=current_user.id,
        data=payload,
    )


@router.get("/payouts", response_model=List[PayoutRequestResponse])
def list_payout_requests(
    status_filter: Union[str, None] = Query(
        None,
        description="Optional filter by payout status (e.g., pending, approved, paid).",
    ),
    start_date: Union[Date, None] = Query(
        None,
        description="Optional start Date for payout requests (inclusive).",
    ),
    end_date: Union[Date, None] = Query(
        None,
        description="Optional end Date for payout requests (inclusive).",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> List[PayoutRequestResponse]:
    """
    Admin endpoint: list payout requests with optional filters.
    """
    service = _get_service(session)
    # Expected:
    #   list_payout_requests(
    #       status: Optional[str],
    #       start_date: Optional[Date],
    #       end_date: Optional[Date],
    #   ) -> list[PayoutRequestResponse]
    return service.list_payout_requests(
        status=status_filter,
        start_date=start_date,
        end_date=end_date,
    )