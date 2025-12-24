"""
Room Availability Service

Provides availability checks and availability calendars.
"""

from __future__ import annotations

from typing import List
from uuid import UUID
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.room import RoomAvailabilityRepository
from app.schemas.room import (
    RoomAvailabilityRequest,
    AvailabilityResponse,
    AvailabilityCalendar,
    BulkAvailabilityRequest,
)
from app.core.exceptions import ValidationException


class RoomAvailabilityService:
    """
    High-level service for room availability.

    Responsibilities:
    - Run availability checks
    - Build availability calendars
    - Handle bulk availability checks across hostels
    """

    def __init__(
        self,
        availability_repo: RoomAvailabilityRepository,
    ) -> None:
        self.availability_repo = availability_repo

    def check_availability(
        self,
        db: Session,
        request: RoomAvailabilityRequest,
    ) -> AvailabilityResponse:
        """
        Check availability for one hostel/date range.
        """
        data = self.availability_repo.check_availability(db, request)
        return AvailabilityResponse.model_validate(data)

    def get_availability_calendar(
        self,
        db: Session,
        room_id: UUID,
        year: int,
        month: int,
    ) -> AvailabilityCalendar:
        """
        Build a monthly availability calendar for a room.
        """
        data = self.availability_repo.get_calendar_for_room(
            db=db,
            room_id=room_id,
            year=year,
            month=month,
        )
        if not data:
            raise ValidationException("Calendar data not available for room")
        return AvailabilityCalendar.model_validate(data)

    def bulk_check_availability(
        self,
        db: Session,
        request: BulkAvailabilityRequest,
    ) -> List[AvailabilityResponse]:
        """
        Check availability across multiple hostels.
        """
        raw = self.availability_repo.bulk_check_availability(db, request)
        return [AvailabilityResponse.model_validate(r) for r in raw]