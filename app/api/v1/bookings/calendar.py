from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.booking.booking_calendar import (
    CalendarView,
    AvailabilityCalendar,
)
from app.services.booking.booking_calendar_service import BookingCalendarService

router = APIRouter(prefix="/bookings/calendar", tags=["bookings:calendar"])


def get_calendar_service(db: Session = Depends(deps.get_db)) -> BookingCalendarService:
    return BookingCalendarService(db=db)


@router.get(
    "/month",
    response_model=CalendarView,
    summary="Get monthly booking calendar",
)
def get_month_view(
    hostel_id: str = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: BookingCalendarService = Depends(get_calendar_service),
) -> Any:
    return service.get_month_view(hostel_id, year, month)


@router.get(
    "/availability",
    response_model=AvailabilityCalendar,
    summary="Get availability calendar",
)
def get_availability_calendar(
    hostel_id: str = Query(...),
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    _admin=Depends(deps.get_admin_user),
    service: BookingCalendarService = Depends(get_calendar_service),
) -> Any:
    return service.get_availability_calendar(hostel_id, start_date, end_date)