# app/api/v1/subscriptions/upgrade.py
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.subscription import SubscriptionUpgradeService
from app.schemas.subscription.subscription_upgrade import (
    UpgradeRequest,
    UpgradePreview,
    DowngradeRequest,
)
from app.schemas.subscription.subscription_response import SubscriptionResponse
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Subscription - Upgrade"])


def _get_service(session: Session) -> SubscriptionUpgradeService:
    uow = UnitOfWork(session)
    return SubscriptionUpgradeService(uow)


@router.post("/{subscription_id}/preview", response_model=UpgradePreview)
def preview_upgrade(
    subscription_id: UUID,
    payload: UpgradeRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> UpgradePreview:
    """
    Preview financial impact of upgrading a subscription (proration, etc.).

    Expected service method:
        preview_upgrade(subscription_id: UUID, data: UpgradeRequest) -> UpgradePreview
    """
    service = _get_service(session)
    return service.preview_upgrade(
        subscription_id=subscription_id,
        data=payload,
    )


@router.post("/{subscription_id}/apply", response_model=SubscriptionResponse)
def apply_upgrade(
    subscription_id: UUID,
    payload: UpgradeRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SubscriptionResponse:
    """
    Apply an upgrade to a subscription.

    Expected service method:
        apply_upgrade(subscription_id: UUID, data: UpgradeRequest) -> SubscriptionResponse
    """
    service = _get_service(session)
    return service.apply_upgrade(
        subscription_id=subscription_id,
        data=payload,
    )


@router.post("/{subscription_id}/downgrade", response_model=SubscriptionResponse)
def apply_downgrade(
    subscription_id: UUID,
    payload: DowngradeRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SubscriptionResponse:
    """
    Apply a downgrade to a subscription.

    Expected service method:
        apply_downgrade(subscription_id: UUID, data: DowngradeRequest) -> SubscriptionResponse
    """
    service = _get_service(session)
    return service.apply_downgrade(
        subscription_id=subscription_id,
        data=payload,
    )