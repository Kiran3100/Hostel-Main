# app/api/v1/payments/refunds.py
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.payment import RefundService
from app.schemas.payment.payment_refund import (
    RefundRequest,
    RefundResponse,
    RefundApproval,
    RefundList,
    RefundListItem,
)
from . import CurrentUser, get_current_admin_or_staff

router = APIRouter(tags=["Payments - Refunds"])


def _get_service(session: Session) -> RefundService:
    uow = UnitOfWork(session)
    return RefundService(uow)


@router.post("/", response_model=RefundResponse, status_code=status.HTTP_201_CREATED)
def create_refund_request(
    payload: RefundRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> RefundResponse:
    """
    Create a refund request for a payment (admin/staff).
    """
    service = _get_service(session)
    # Expected: create_refund_request(requester_id: UUID, data: RefundRequest) -> RefundResponse
    return service.create_refund_request(
        requester_id=current_user.id,
        data=payload,
    )


@router.get("/", response_model=RefundList)
def list_refunds(
    status_filter: str | None = Query(
        None,
        description="Optional refund status filter",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> RefundList:
    """
    List refund requests with basic totals.
    """
    service = _get_service(session)
    # Expected: list_refunds(status: Optional[str]) -> RefundList
    return service.list_refunds(status=status_filter)


@router.get("/{refund_id}", response_model=RefundResponse)
def get_refund(
    refund_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> RefundResponse:
    """
    Get a single refund by ID.
    """
    service = _get_service(session)
    # Expected: get_refund(refund_id: UUID) -> RefundResponse
    return service.get_refund(refund_id=refund_id)


@router.post("/{refund_id}/approve", response_model=RefundResponse)
def approve_refund(
    refund_id: UUID,
    payload: RefundApproval,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> RefundResponse:
    """
    Approve or reject a refund request.
    """
    service = _get_service(session)
    # Expected: approve_refund(refund_id: UUID, approver_id: UUID, data: RefundApproval) -> RefundResponse
    return service.approve_refund(
        refund_id=refund_id,
        approver_id=current_user.id,
        data=payload,
    )