from typing import Any, List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.booking.booking_approval import (
    BookingApprovalRequest,
    ApprovalResponse,
    RejectionRequest,
    BulkApprovalRequest,
    ApprovalSettings,
)
from app.services.booking.booking_approval_service import BookingApprovalService

router = APIRouter(prefix="/bookings/approval", tags=["bookings:approval"])


def get_approval_service(db: Session = Depends(deps.get_db)) -> BookingApprovalService:
    return BookingApprovalService(db=db)


@router.post(
    "/{booking_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve booking",
)
def approve_booking(
    booking_id: str,
    payload: BookingApprovalRequest,
    _admin=Depends(deps.get_admin_user),
    service: BookingApprovalService = Depends(get_approval_service),
) -> Any:
    return service.approve(booking_id, payload, approver_id=_admin.id)


@router.post(
    "/{booking_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject booking",
)
def reject_booking(
    booking_id: str,
    payload: RejectionRequest,
    _admin=Depends(deps.get_admin_user),
    service: BookingApprovalService = Depends(get_approval_service),
) -> Any:
    return service.reject(booking_id, payload, rejector_id=_admin.id)


@router.post(
    "/bulk",
    response_model=List[ApprovalResponse],
    summary="Bulk approve bookings",
)
def bulk_approve(
    payload: BulkApprovalRequest,
    _admin=Depends(deps.get_admin_user),
    service: BookingApprovalService = Depends(get_approval_service),
) -> Any:
    return service.bulk_approve(payload, approver_id=_admin.id)


@router.get(
    "/settings/{hostel_id}",
    response_model=ApprovalSettings,
    summary="Get approval settings",
)
def get_approval_settings(
    hostel_id: str,
    _admin=Depends(deps.get_admin_user),
    service: BookingApprovalService = Depends(get_approval_service),
) -> Any:
    return service.get_settings(hostel_id)


@router.put(
    "/settings/{hostel_id}",
    response_model=ApprovalSettings,
    summary="Update approval settings",
)
def update_approval_settings(
    hostel_id: str,
    payload: ApprovalSettings,
    _admin=Depends(deps.get_admin_user),
    service: BookingApprovalService = Depends(get_approval_service),
) -> Any:
    return service.update_settings(hostel_id, payload)