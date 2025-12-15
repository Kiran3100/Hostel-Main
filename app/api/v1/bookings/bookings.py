# api/v1/bookings/bookings.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.booking.booking_base import BookingCreate, BookingUpdate
from app.schemas.booking.booking_response import (
    BookingDetail,
    BookingListItem,
    BookingConfirmation,
)
from app.schemas.booking.booking_filters import (
    BookingFilterParams,
    BookingSearchRequest,
)
from app.schemas.common.pagination import PaginatedResponse
from app.services.common.unit_of_work import UnitOfWork
from app.services.booking import BookingService

router = APIRouter()


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/",
    response_model=PaginatedResponse[BookingListItem],
    summary="List bookings",
)
async def list_bookings(
    filters: BookingFilterParams = Depends(),
    uow: UnitOfWork = Depends(get_uow),
) -> PaginatedResponse[BookingListItem]:
    """
    List bookings using flexible filters (hostel, status, date range, source, etc.)
    with pagination and sorting.
    """
    service = BookingService(uow)
    try:
        return service.list_bookings(filters=filters)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/",
    response_model=BookingDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new booking",
)
async def create_booking(
    payload: BookingCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> BookingDetail:
    """
    Create a new booking (internal/admin or system-side).

    Validates amounts and requested room type using BookingCreate.
    """
    service = BookingService(uow)
    try:
        return service.create_booking(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{booking_id}",
    response_model=BookingDetail,
    summary="Get booking details",
)
async def get_booking(
    booking_id: UUID = Path(..., description="Booking ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> BookingDetail:
    """
    Retrieve detailed booking information including hostel, amounts, status history,
    and assignment (if any).
    """
    service = BookingService(uow)
    try:
        return service.get_booking(booking_id=booking_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{booking_id}",
    response_model=BookingDetail,
    summary="Update a booking",
)
async def update_booking(
    booking_id: UUID = Path(..., description="Booking ID"),
    payload: BookingUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> BookingDetail:
    """
    Partially update a booking (dates, duration, notes, status, etc.).
    """
    service = BookingService(uow)
    try:
        return service.update_booking(
            booking_id=booking_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/search",
    response_model=PaginatedResponse[BookingListItem],
    summary="Search bookings",
)
async def search_bookings(
    payload: BookingSearchRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> PaginatedResponse[BookingListItem]:
    """
    Structured booking search endpoint (richer than simple filters),
    e.g. multi-field search, complex status/date logic.
    """
    service = BookingService(uow)
    try:
        return service.search_bookings(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{booking_id}/confirmation",
    response_model=BookingConfirmation,
    summary="Get booking confirmation payload",
)
async def get_booking_confirmation(
    booking_id: UUID = Path(..., description="Booking ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> BookingConfirmation:
    """
    Retrieve a confirmation payload for the booking (for emails/PDF, guest view).
    """
    service = BookingService(uow)
    try:
        return service.get_confirmation(booking_id=booking_id)
    except ServiceError as exc:
        raise _map_service_error(exc)