# app/api/v1/subscriptions/cancellation.py
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.subscription import SubscriptionService
from app.schemas.subscription.subscription_cancellation import (
    CancellationRequest,
    CancellationResponse,
)
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Subscription - Cancellation"])


def _get_service(session: Session) -> SubscriptionService:
    uow = UnitOfWork(session)
    return SubscriptionService(uow)


@router.post("/{subscription_id}", response_model=CancellationResponse)
def cancel_subscription(
    subscription_id: UUID,
    payload: CancellationRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> CancellationResponse:
    """
    Cancel a subscription and compute any applicable refunds / end dates.

    Expected service method:
        cancel_subscription(subscription_id: UUID, data: CancellationRequest) -> CancellationResponse
    """
    service = _get_service(session)
    return service.cancel_subscription(
        subscription_id=subscription_id,
        data=payload,
    )