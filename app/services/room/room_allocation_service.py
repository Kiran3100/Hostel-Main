"""
Room Allocation Service

Provides higher-level algorithms to allocate rooms/beds to bookings or students.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.room import (
    RoomAvailabilityRepository,
    BedAssignmentRepository,
)
from app.repositories.booking import BookingRepository
from app.schemas.room import RoomAvailabilityRequest, AvailabilityResponse
from app.core.exceptions import ValidationException, BusinessLogicException


class RoomAllocationService:
    """
    High-level service for automatic room/bed allocation.

    Responsibilities:
    - Suggest best room/bed for a given booking or request
    - Reserve and/or assign beds atomically
    """

    def __init__(
        self,
        availability_repo: RoomAvailabilityRepository,
        bed_assignment_repo: BedAssignmentRepository,
        booking_repo: BookingRepository,
    ) -> None:
        self.availability_repo = availability_repo
        self.bed_assignment_repo = bed_assignment_repo
        self.booking_repo = booking_repo

    def suggest_allocation_for_booking(
        self,
        db: Session,
        booking_id: UUID,
    ) -> Dict[str, Any]:
        """
        Suggest a room/bed for a given booking.

        Returns a dict with `room_id`, `bed_id`, and optionally scoring info.
        """
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValidationException("Booking not found")

        if not booking.hostel_id or not booking.preferred_check_in_date:
            raise BusinessLogicException("Booking is missing hostel or check-in date")

        request = RoomAvailabilityRequest(
            hostel_id=booking.hostel_id,
            check_in_date=booking.preferred_check_in_date,
            stay_duration_months=booking.stay_duration_months,
            room_type=booking.room_type_requested,
        )

        availability_dict = self.availability_repo.check_availability(db, request)
        availability = AvailabilityResponse.model_validate(availability_dict)

        if not availability.available_rooms:
            raise BusinessLogicException("No available rooms for requested criteria")

        # Simple heuristic: choose room with most available beds
        best_room = max(
            availability.available_rooms,
            key=lambda r: r.available_beds,
        )

        # You could add more sophisticated scoring here (price, floor, amenities)
        return {
            "room_id": best_room.room_id,
            "bed_id": best_room.suggested_bed_id,
            "score": best_room.match_score,
        }

    def reserve_allocation_for_booking(
        self,
        db: Session,
        booking_id: UUID,
    ) -> Dict[str, Any]:
        """
        Suggest and reserve a bed for a booking in one call.

        Delegates reservation to RoomAvailabilityRepository / BedAssignmentRepository.
        """
        suggestion = self.suggest_allocation_for_booking(db, booking_id)

        reservation = self.bed_assignment_repo.reserve_bed_for_booking(
            db=db,
            booking_id=booking_id,
            room_id=suggestion["room_id"],
            bed_id=suggestion["bed_id"],
        )

        return {
            "room_id": suggestion["room_id"],
            "bed_id": suggestion["bed_id"],
            "reservation_id": reservation.id,
        }