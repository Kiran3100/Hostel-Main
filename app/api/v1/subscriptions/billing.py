# app/api/v1/subscriptions/billing.py
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.subscription import SubscriptionBillingService
from app.schemas.subscription.subscription_billing import (
    BillingCycleInfo,
    GenerateInvoiceRequest,
    InvoiceInfo,
)
from app.schemas.subscription.subscription_response import BillingHistory
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Subscription - Billing"])


def _get_service(session: Session) -> SubscriptionBillingService:
    uow = UnitOfWork(session)
    return SubscriptionBillingService(uow)


@router.get("/{subscription_id}/cycle", response_model=BillingCycleInfo)
def get_billing_cycle_info(
    subscription_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BillingCycleInfo:
    """
    Get billing cycle info for a subscription.

    Expected service method:
        get_billing_cycle_info(subscription_id: UUID) -> BillingCycleInfo
    """
    service = _get_service(session)
    return service.get_billing_cycle_info(subscription_id=subscription_id)


@router.post("/{subscription_id}/invoices", response_model=InvoiceInfo)
def generate_invoice(
    subscription_id: UUID,
    payload: GenerateInvoiceRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> InvoiceInfo:
    """
    Generate an invoice for a subscription.

    Expected service method:
        generate_invoice(subscription_id: UUID, data: GenerateInvoiceRequest) -> InvoiceInfo
    """
    service = _get_service(session)
    return service.generate_invoice(
        subscription_id=subscription_id,
        data=payload,
    )


@router.get("/{subscription_id}/history", response_model=BillingHistory)
def get_billing_history(
    subscription_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BillingHistory:
    """
    Get billing history for a subscription.

    Expected service method:
        get_billing_history(subscription_id: UUID) -> BillingHistory
    """
    service = _get_service(session)
    return service.get_billing_history(subscription_id=subscription_id)