# api/v1/bookings/modification.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.booking.booking_modification import (
    ModificationRequest,
    ModificationResponse,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.booking import BookingModificationService

router = APIRouter(prefix="/modification")


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
    response_model=ModificationResponse,
    summary="Preview booking modification",
)
async def preview_modification(
    booking_id: UUID = Path(..., description="Booking ID"),
    payload: ModificationRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ModificationResponse:
    """
    Preview the impact (price, duration) of modifying a booking.
    """
    service = BookingModificationService(uow)
    try:
        return service.preview_modification(
            booking_id=booking_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bookings/{booking_id}/apply",
    response_model=ModificationResponse,
    summary="Apply booking modification",
)
async def apply_modification(
    booking_id: UUID = Path(..., description="Booking ID"),
    payload: ModificationRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ModificationResponse:
    """
    Apply a modification to a booking (after optional approval).
    """
    service = BookingModificationService(uow)
    try:
        return service.apply_modification(
            booking_id=booking_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)