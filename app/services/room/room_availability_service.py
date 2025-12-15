# app/services/room/room_availability_service.py
from __future__ import annotations

from calendar import monthrange
from datetime import timedelta
from datetime import date as Date
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import RoomRepository, BedRepository, HostelRepository, StudentRepository
from app.schemas.room.room_availability import (
    RoomAvailabilityRequest,
    AvailabilityResponse,
    AvailableRoom,
    AvailabilityCalendar,
    DayAvailability,
    BookingInfo,
)
from app.schemas.common.enums import RoomType, BedStatus
from app.services.common import UnitOfWork, errors


class RoomAvailabilityService:
    """
    Room availability service (simplified):

    - Check current availability for a hostel/date/room_type.
    - Build a naive monthly availability calendar per room.

    NOTE:
    For accurate future occupancy, integrate with booking/schedule data.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_bed_repo(self, uow: UnitOfWork) -> BedRepository:
        return uow.get_repo(BedRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _add_months(self, d: Date, months: int) -> Date:
        month = d.month - 1 + months
        year = d.year + month // 12
        month = month % 12 + 1
        day = min(
            d.day,
            monthrange(year, month)[1],
        )
        return Date(year, month, day)

    # ------------------------------------------------------------------ #
    # Availability
    # ------------------------------------------------------------------ #
    def check_availability(self, req: RoomAvailabilityRequest) -> AvailabilityResponse:
        """
        Compute availability for given hostel/date/room_type.

        This implementation uses current bed occupancy only (no future bookings).
        """
        check_in = req.check_in_date
        check_out = self._add_months(check_in, req.duration_months)

        with UnitOfWork(self._session_factory) as uow:
            room_repo = self._get_room_repo(uow)
            bed_repo = self._get_bed_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(req.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {req.hostel_id} not found")

            rooms = room_repo.list_for_hostel(
                hostel_id=req.hostel_id,
                only_available=True,
                room_type=req.room_type,
            )
            room_ids = [r.id for r in rooms]
            bed_map: Dict[UUID, List] = {rid: [] for rid in room_ids}
            all_beds = bed_repo.get_multi(filters={"room_id": room_ids}) if room_ids else []
            for b in all_beds:
                bed_map.setdefault(b.room_id, []).append(b)

        available_rooms: List[AvailableRoom] = []
        total_available_beds = 0

        for r in rooms:
            beds = bed_map.get(r.id, [])
            available_beds = sum(
                1 for b in beds
                if b.current_student_id is None and b.status == BedStatus.AVAILABLE
            )
            if available_beds <= 0:
                continue

            total_available_beds += available_beds

            available_rooms.append(
                AvailableRoom(
                    room_id=r.id,
                    room_number=r.room_number,
                    room_type=r.room_type,
                    floor_number=r.floor_number,
                    available_beds=available_beds,
                    total_beds=r.total_beds,
                    price_monthly=r.price_monthly,
                    is_ac=r.is_ac,
                    has_attached_bathroom=r.has_attached_bathroom,
                    amenities=r.amenities or [],
                    room_images=r.room_images or [],
                )
            )

        return AvailabilityResponse(
            hostel_id=req.hostel_id,
            check_in_date=check_in,
            check_out_date=check_out,
            available_rooms=available_rooms,
            total_available_beds=total_available_beds,
            has_availability=total_available_beds > 0,
        )

    # ------------------------------------------------------------------ #
    # Calendar
    # ------------------------------------------------------------------ #
    def get_availability_calendar(
        self,
        room_id: UUID,
        month: str,
    ) -> AvailabilityCalendar:
        """
        Naive availability calendar for a room.

        Assumes current occupancy is constant over the month (no bookings).
        """
        try:
            year, m = map(int, month.split("-"))
        except ValueError:
            raise errors.ValidationError("month must be in 'YYYY-MM' format")

        start = Date(year, m, 1)
        last_day = monthrange(year, m)[1]
        end = Date(year, m, last_day)

        with UnitOfWork(self._session_factory) as uow:
            room_repo = self._get_room_repo(uow)
            bed_repo = self._get_bed_repo(uow)
            student_repo = self._get_student_repo(uow)

            room = room_repo.get(room_id)
            if room is None:
                raise errors.NotFoundError(f"Room {room_id} not found")

            beds = bed_repo.get_multi(filters={"room_id": room.id})
            total_beds = room.total_beds
            available_beds = sum(
                1 for b in beds
                if b.current_student_id is None and b.status == BedStatus.AVAILABLE
            )

        # For now we assume occupancy static across the month.
        availability: Dict[str, DayAvailability] = {}
        cur = start
        while cur <= end:
            availability[cur.isoformat()] = DayAvailability(
                date=cur,
                available_beds=available_beds,
                total_beds=total_beds,
                is_available=available_beds > 0,
                bookings=[],  # no booking data wired yet
            )
            cur += timedelta(days=1)

        return AvailabilityCalendar(
            room_id=room.id,
            room_number=room.room_number,
            month=month,
            availability=availability,
        )