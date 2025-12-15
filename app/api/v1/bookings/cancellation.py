# api/v1/bookings/cancellation.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.booking.booking_cancellation import (
    CancellationRequest,
    CancellationResponse,
    RefundCalculation,
    BulkCancellation,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.booking import BookingCancellationService

router = APIRouter(prefix="/cancellation")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/bookings/{booking_id}/preview",
    response_model=RefundCalculation,
    summary="Preview cancellation refund for a booking",
)
async def preview_cancellation(
    booking_id: UUID = Path(..., description="Booking ID"),
    payload: CancellationRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> RefundCalculation:
    """
    Preview refund and charges for a potential cancellation without applying it.
    """
    service = BookingCancellationService(uow)
    try:
        return service.preview_cancellation(
            booking_id=booking_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bookings/{booking_id}",
    response_model=CancellationResponse,
    summary="Cancel a booking",
)
async def cancel_booking(
    booking_id: UUID = Path(..., description="Booking ID"),
    payload: CancellationRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> CancellationResponse:
    """
    Cancel a booking and optionally trigger refund execution.
    """
    service = BookingCancellationService(uow)
    try:
        return service.cancel_booking(
            booking_id=booking_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bulk",
    response_model=List[CancellationResponse],
    summary="Bulk cancel bookings",
)
async def bulk_cancel_bookings(
    payload: BulkCancellation,
    uow: UnitOfWork = Depends(get_uow),
) -> List[CancellationResponse]:
    """
    Bulk cancel multiple bookings and compute/apply refunds.
    """
    service = BookingCancellationService(uow)
    try:
        return service.bulk_cancel(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)