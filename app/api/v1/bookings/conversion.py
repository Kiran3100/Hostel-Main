# api/v1/bookings/conversion.py
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.booking.booking_conversion import (
    ConvertToStudentRequest,
    ConversionResponse,
    BulkConversion,
    ConversionRollback,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.booking import BookingConversionService

router = APIRouter(prefix="/conversion")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/bookings/{booking_id}",
    response_model=ConversionResponse,
    summary="Convert booking into student",
)
async def convert_booking(
    booking_id: UUID = Path(..., description="Booking ID"),
    payload: ConvertToStudentRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ConversionResponse:
    """
    Convert a confirmed booking into a student profile and assign a bed.
    """
    service = BookingConversionService(uow)
    try:
        return service.convert_booking(
            booking_id=booking_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bulk",
    response_model=List[ConversionResponse],
    summary="Bulk convert bookings into students",
)
async def bulk_convert_bookings(
    payload: BulkConversion,
    uow: UnitOfWork = Depends(get_uow),
) -> List[ConversionResponse]:
    """
    Bulk convert multiple bookings into students.
    """
    service = BookingConversionService(uow)
    try:
        return service.bulk_convert(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/rollback",
    response_model=ConversionResponse,
    summary="Rollback a booking conversion",
)
async def rollback_conversion(
    payload: ConversionRollback,
    uow: UnitOfWork = Depends(get_uow),
) -> ConversionResponse:
    """
    Rollback a prior conversion (if allowed), reverting student/bed assignment.
    """
    service = BookingConversionService(uow)
    try:
        return service.rollback_conversion(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)