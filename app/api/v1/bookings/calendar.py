# api/v1/bookings/calendar.py
from __future__ import annotations

from datetime import date as Date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.booking.booking_calendar import (
    CalendarView,
    AvailabilityCalendar,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.booking import BookingCalendarService

router = APIRouter(prefix="/calendar")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/hostels/{hostel_id}",
    response_model=CalendarView,
    summary="Get hostel booking calendar",
)
async def get_hostel_calendar(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    period_start: Date = Query(..., description="Start Date (inclusive)"),
    period_end: Date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> CalendarView:
    """
    Build a booking calendar view for a hostel (check-in/out events per day).
    """
    service = BookingCalendarService(uow)
    try:
        return service.get_hostel_calendar(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/rooms/{room_id}",
    response_model=CalendarView,
    summary="Get room booking calendar",
)
async def get_room_calendar(
    room_id: UUID = Path(..., description="Room ID"),
    period_start: Date = Query(..., description="Start Date (inclusive)"),
    period_end: Date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> CalendarView:
    """
    Build a booking calendar view for a specific room.
    """
    service = BookingCalendarService(uow)
    try:
        return service.get_room_calendar(
            room_id=room_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/availability",
    response_model=AvailabilityCalendar,
    summary="Get hostel availability calendar",
)
async def get_hostel_availability_calendar(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    period_start: Date = Query(..., description="Start Date (inclusive)"),
    period_end: Date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> AvailabilityCalendar:
    """
    Return an availability calendar for a hostel, showing available beds per day.
    """
    service = BookingCalendarService(uow)
    try:
        return service.get_availability_calendar(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)