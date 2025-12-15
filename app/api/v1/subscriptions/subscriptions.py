# app/api/v1/subscriptions/subscriptions.py
from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.subscription import SubscriptionService
from app.schemas.subscription.subscription_base import (
    SubscriptionCreate,
    SubscriptionUpdate,
)
from app.schemas.subscription.subscription_response import (
    SubscriptionResponse,
)
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Subscription - Subscriptions"])


def _get_service(session: Session) -> SubscriptionService:
    uow = UnitOfWork(session)
    return SubscriptionService(uow)


@router.get("/", response_model=List[SubscriptionResponse])
def list_subscriptions(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Optionally filter subscriptions by hostel ID.",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[SubscriptionResponse]:
    """
    List subscriptions, optionally filtered by hostel.

    Expected service method:
        list_subscriptions(hostel_id: Optional[UUID]) -> list[SubscriptionResponse]
    """
    service = _get_service(session)
    return service.list_subscriptions(hostel_id=hostel_id)


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(
    subscription_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SubscriptionResponse:
    """
    Get details of a single subscription.

    Expected service method:
        get_subscription(subscription_id: UUID) -> SubscriptionResponse
    """
    service = _get_service(session)
    return service.get_subscription(subscription_id=subscription_id)


@router.post(
    "/",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription(
    payload: SubscriptionCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SubscriptionResponse:
    """
    Create a new hostel subscription.

    Expected service method:
        create_subscription(data: SubscriptionCreate) -> SubscriptionResponse
    """
    service = _get_service(session)
    return service.create_subscription(data=payload)


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
def update_subscription(
    subscription_id: UUID,
    payload: SubscriptionUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SubscriptionResponse:
    """
    Update an existing subscription.

    Expected service method:
        update_subscription(subscription_id: UUID, data: SubscriptionUpdate) -> SubscriptionResponse
    """
    service = _get_service(session)
    return service.update_subscription(
        subscription_id=subscription_id,
        data=payload,
    )


@router.get("/hostels/{hostel_id}/active", response_model=Union[SubscriptionResponse, None])
def get_active_subscription_for_hostel(
    hostel_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> Union[SubscriptionResponse, None]:
    """
    Get the active subscription for a hostel (if any).

    Expected service method:
        get_active_subscription_for_hostel(hostel_id: UUID) -> Optional[SubscriptionResponse]
    """
    service = _get_service(session)
    return service.get_active_subscription_for_hostel(hostel_id=hostel_id)