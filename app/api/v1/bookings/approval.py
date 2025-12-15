# api/v1/bookings/approval.py
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.booking.booking_approval import (
    BookingApprovalRequest,
    ApprovalResponse,
    RejectionRequest,
    BulkApprovalRequest,
    ApprovalSettings,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.booking import BookingApprovalService

router = APIRouter(prefix="/approval")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/bookings/{booking_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve a booking",
)
async def approve_booking(
    booking_id: UUID = Path(..., description="Booking ID"),
    payload: BookingApprovalRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalResponse:
    """
    Approve a booking, confirm pricing, and optionally require advance payment.
    """
    service = BookingApprovalService(uow)
    try:
        return service.approve_booking(
            booking_id=booking_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bookings/{booking_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject a booking",
)
async def reject_booking(
    booking_id: UUID = Path(..., description="Booking ID"),
    payload: RejectionRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalResponse:
    """
    Reject a booking with structured rejection reasons and potential alternatives.
    """
    service = BookingApprovalService(uow)
    try:
        return service.reject_booking(
            booking_id=booking_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bulk",
    response_model=List[ApprovalResponse],
    summary="Bulk approve/reject bookings",
)
async def bulk_approve_bookings(
    payload: BulkApprovalRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> List[ApprovalResponse]:
    """
    Bulk approve or reject multiple bookings in a single request.
    """
    service = BookingApprovalService(uow)
    try:
        return service.bulk_approve(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/settings",
    response_model=ApprovalSettings,
    summary="Get booking approval settings",
)
async def get_approval_settings(
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalSettings:
    """
    Get automated approval settings (thresholds, rules).
    """
    service = BookingApprovalService(uow)
    try:
        return service.get_settings()
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.put(
    "/settings",
    response_model=ApprovalSettings,
    summary="Update booking approval settings",
)
async def update_approval_settings(
    payload: ApprovalSettings,
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalSettings:
    """
    Update automated approval settings.
    """
    service = BookingApprovalService(uow)
    try:
        return service.update_settings(settings=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)