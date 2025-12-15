# app/services/booking/booking_calendar_service.py
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, List, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import BookingRepository
from app.repositories.core import RoomRepository
from app.schemas.booking import (
    CalendarView,
    DayBookings,
    BookingEvent,
    AvailabilityCalendar,
    DayAvailability,
)
from app.schemas.common.enums import BookingStatus
from app.services.common import UnitOfWork, errors


class BookingCalendarService:
    """
    Generate calendar views and availability for bookings.

    NOTE:
    - This is a read-only service over txn_booking and rooms.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_booking_repo(self, uow: UnitOfWork) -> BookingRepository:
        return uow.get_repo(BookingRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    # ------------------------------------------------------------------ #
    # Calendar view for a month
    # ------------------------------------------------------------------ #
    def get_calendar_view(
        self,
        hostel_id: UUID,
        year: int,
        month: int,
    ) -> CalendarView:
        from calendar import monthrange

        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])

        with UnitOfWork(self._session_factory) as uow:
            booking_repo = self._get_booking_repo(uow)

            bookings = booking_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": hostel_id},
            )

        # Filter bookings that intersect with the month
        relevant = []
        for b in bookings:
            ci = b.preferred_check_in_date
            co = ci + timedelta(days=30 * b.stay_duration_months)
            if co < first_day or ci > last_day:
                continue
            relevant.append(b)

        days_map: Dict[str, DayBookings] = {}
        available_rooms_by_date: Dict[str, int] = {}

        for offset in range((last_day - first_day).days + 1):
            d = first_day + timedelta(days=offset)
            key = d.isoformat()
            days_map[key] = DayBookings(
                day_date=d,
                check_ins=[],
                check_outs=[],
                pending_bookings=[],
                available_beds=0,
                total_beds=0,
            )
            available_rooms_by_date[key] = 0

        for b in relevant:
            ci = b.preferred_check_in_date
            co = ci + timedelta(days=30 * b.stay_duration_months)

            # Check-ins
            ci_key = ci.isoformat()
            if ci_key in days_map:
                days_map[ci_key].check_ins.append(
                    BookingEvent(
                        booking_id=b.id,
                        booking_reference=f"BKG-{str(b.id)[:8].upper()}",
                        guest_name=b.guest_name,
                        room_number=None,
                        room_type=b.room_type_requested.value if hasattr(b.room_type_requested, "value") else str(b.room_type_requested),
                        status=b.booking_status,
                        is_check_in=True,
                        is_check_out=False,
                    )
                )

            # Check-outs
            co_key = co.isoformat()
            if co_key in days_map:
                days_map[co_key].check_outs.append(
                    BookingEvent(
                        booking_id=b.id,
                        booking_reference=f"BKG-{str(b.id)[:8].upper()}",
                        guest_name=b.guest_name,
                        room_number=None,
                        room_type=b.room_type_requested.value if hasattr(b.room_type_requested, "value") else str(b.room_type_requested),
                        status=b.booking_status,
                        is_check_in=False,
                        is_check_out=True,
                    )
                )

            # Pending bookings
            if b.booking_status == BookingStatus.PENDING:
                key = b.preferred_check_in_date.isoformat()
                if key in days_map:
                    days_map[key].pending_bookings.append(
                        BookingEvent(
                            booking_id=b.id,
                            booking_reference=f"BKG-{str(b.id)[:8].upper()}",
                            guest_name=b.guest_name,
                            room_number=None,
                            room_type=b.room_type_requested.value if hasattr(b.room_type_requested, "value") else str(b.room_type_requested),
                            status=b.booking_status,
                            is_check_in=False,
                            is_check_out=False,
                        )
                    )

        # available_rooms_by_date is left 0; you can enrich it using room occupancy if needed
        return CalendarView(
            hostel_id=hostel_id,
            month=f"{year:04d}-{month:02d}",
            days=days_map,
            total_check_ins=sum(len(d.check_ins) for d in days_map.values()),
            total_check_outs=sum(len(d.check_outs) for d in days_map.values()),
            peak_occupancy_date=None,
            available_rooms_by_date=available_rooms_by_date,
        )

    # ------------------------------------------------------------------ #
    # Availability calendar (per room)
    # ------------------------------------------------------------------ #
    def get_availability_calendar(
        self,
        room_id: UUID,
        year: int,
        month: int,
    ) -> AvailabilityCalendar:
        from calendar import monthrange

        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])

        with UnitOfWork(self._session_factory) as uow:
            booking_repo = self._get_booking_repo(uow)
            room_repo = self._get_room_repo(uow)

            room = room_repo.get(room_id)
            if room is None:
                raise errors.NotFoundError(f"Room {room_id} not found")

            bookings = booking_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"room_id": room_id},
            )

        availability: Dict[str, DayAvailability] = {}
        for offset in range((last_day - first_day).days + 1):
            d = first_day + timedelta(days=offset)
            key = d.isoformat()
            availability[key] = DayAvailability(
                day_date=d,
                total_beds=room.total_beds,
                available_beds=room.total_beds,
                booked_beds=0,
                is_fully_booked=False,
                active_bookings=[],
            )

        from app.schemas.booking.booking_calendar import BookingInfo  # avoid circular imports

        for b in bookings:
            ci = b.preferred_check_in_date
            co = ci + timedelta(days=30 * b.stay_duration_months)
            for offset in range((co - ci).days):
                d = ci + timedelta(days=offset)
                if d < first_day or d > last_day:
                    continue
                key = d.isoformat()
                if key not in availability:
                    continue
                day_avail = availability[key]
                day_avail.available_beds = max(0, day_avail.available_beds - 1)
                day_avail.booked_beds = day_avail.total_beds - day_avail.available_beds
                day_avail.is_fully_booked = day_avail.available_beds == 0
                day_avail.active_bookings.append(b.id)

        return AvailabilityCalendar(
            room_id=room_id,
            room_number=room.room_number,
            month=f"{year:04d}-{month:02d}",
            availability=availability,
        )