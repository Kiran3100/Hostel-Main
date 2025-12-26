"""
Room Allocation Service

Provides higher-level algorithms to allocate rooms/beds to bookings or students.

Enhancements:
- Improved allocation algorithm with scoring
- Added fallback strategies
- Enhanced error handling and logging
- Support for allocation preferences
- Optimized database queries
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.room import (
    RoomAvailabilityRepository,
    BedAssignmentRepository,
    BedRepository,
)
from app.repositories.booking import BookingRepository
from app.schemas.room import RoomAvailabilityRequest, AvailabilityResponse
from app.core.exceptions import ValidationException, BusinessLogicException

logger = logging.getLogger(__name__)


class RoomAllocationService:
    """
    High-level service for automatic room/bed allocation.

    Responsibilities:
    - Suggest optimal room/bed for a given booking or request
    - Reserve and/or assign beds atomically
    - Apply allocation strategies and preferences
    - Handle allocation conflicts
    
    Performance optimizations:
    - Efficient scoring algorithms
    - Batch availability checks
    - Transaction management
    """

    __slots__ = (
        'availability_repo',
        'bed_assignment_repo',
        'booking_repo',
        'bed_repo',
    )

    def __init__(
        self,
        availability_repo: RoomAvailabilityRepository,
        bed_assignment_repo: BedAssignmentRepository,
        booking_repo: BookingRepository,
        bed_repo: Optional[BedRepository] = None,
    ) -> None:
        """
        Initialize the service with required repositories.

        Args:
            availability_repo: Repository for room availability operations
            bed_assignment_repo: Repository for bed assignment operations
            booking_repo: Repository for booking operations
            bed_repo: Optional bed repository for additional operations
        """
        self.availability_repo = availability_repo
        self.bed_assignment_repo = bed_assignment_repo
        self.booking_repo = booking_repo
        self.bed_repo = bed_repo

    def suggest_allocation_for_booking(
        self,
        db: Session,
        booking_id: UUID,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Suggest optimal room/bed for a given booking with intelligent scoring.

        Scoring considers:
        - Room type match
        - Available beds count
        - Price compatibility
        - Floor preferences
        - Amenities match

        Args:
            db: Database session
            booking_id: UUID of the booking
            preferences: Optional allocation preferences

        Returns:
            Dict containing room_id, bed_id, score, and reasoning

        Raises:
            ValidationException: If booking not found
            BusinessLogicException: If no available rooms match criteria
        """
        try:
            # Retrieve and validate booking
            booking = self._get_booking_or_raise(db, booking_id)
            
            # Validate booking has required fields
            self._validate_booking_for_allocation(booking)
            
            # Build availability request
            request = self._build_availability_request(booking)
            
            # Check availability
            availability_dict = self.availability_repo.check_availability(db, request)
            availability = AvailabilityResponse.model_validate(availability_dict)
            
            if not availability.available_rooms:
                raise BusinessLogicException(
                    f"No available rooms found for booking {booking_id}"
                )
            
            # Score and select best room
            best_allocation = self._select_best_room(
                available_rooms=availability.available_rooms,
                booking=booking,
                preferences=preferences or {},
            )
            
            logger.info(
                f"Suggested allocation for booking {booking_id}: "
                f"Room {best_allocation['room_id']}, Bed {best_allocation['bed_id']}, "
                f"Score: {best_allocation['score']}"
            )
            
            return best_allocation
            
        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error suggesting allocation for booking {booking_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to suggest allocation")

    def reserve_allocation_for_booking(
        self,
        db: Session,
        booking_id: UUID,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Suggest and reserve a bed for a booking in one atomic transaction.

        Args:
            db: Database session
            booking_id: UUID of the booking
            preferences: Optional allocation preferences

        Returns:
            Dict containing room_id, bed_id, reservation_id

        Raises:
            ValidationException: If booking not found
            BusinessLogicException: If reservation fails
        """
        try:
            # Get suggestion
            suggestion = self.suggest_allocation_for_booking(
                db, booking_id, preferences
            )
            
            # Reserve bed atomically
            reservation = self.bed_assignment_repo.reserve_bed_for_booking(
                db=db,
                booking_id=booking_id,
                room_id=suggestion["room_id"],
                bed_id=suggestion["bed_id"],
            )
            
            db.commit()
            
            logger.info(
                f"Reserved allocation for booking {booking_id}: "
                f"Room {suggestion['room_id']}, Bed {suggestion['bed_id']}, "
                f"Reservation {reservation.id}"
            )
            
            return {
                "room_id": suggestion["room_id"],
                "bed_id": suggestion["bed_id"],
                "reservation_id": reservation.id,
                "score": suggestion["score"],
                "reasoning": suggestion.get("reasoning", ""),
            }
            
        except (ValidationException, BusinessLogicException):
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during reservation: {str(e)}")
            raise BusinessLogicException("Failed to reserve allocation")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error during reservation: {str(e)}")
            raise BusinessLogicException("Failed to reserve allocation")

    def suggest_bulk_allocations(
        self,
        db: Session,
        booking_ids: List[UUID],
        preferences: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Suggest allocations for multiple bookings efficiently.

        Args:
            db: Database session
            booking_ids: List of booking UUIDs
            preferences: Optional allocation preferences

        Returns:
            List of allocation suggestions
        """
        try:
            suggestions = []
            
            for booking_id in booking_ids:
                try:
                    suggestion = self.suggest_allocation_for_booking(
                        db, booking_id, preferences
                    )
                    suggestions.append({
                        "booking_id": booking_id,
                        "success": True,
                        **suggestion,
                    })
                except (ValidationException, BusinessLogicException) as e:
                    suggestions.append({
                        "booking_id": booking_id,
                        "success": False,
                        "error": str(e),
                    })
            
            logger.info(
                f"Generated {len(suggestions)} allocation suggestions, "
                f"{sum(1 for s in suggestions if s['success'])} successful"
            )
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error in bulk allocation suggestions: {str(e)}")
            raise BusinessLogicException("Failed to generate bulk allocations")

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _get_booking_or_raise(self, db: Session, booking_id: UUID):
        """Retrieve booking or raise ValidationException."""
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValidationException(f"Booking {booking_id} not found")
        return booking

    def _validate_booking_for_allocation(self, booking) -> None:
        """Validate booking has required fields for allocation."""
        if not booking.hostel_id:
            raise BusinessLogicException(
                f"Booking {booking.id} is missing hostel_id"
            )
        
        if not booking.preferred_check_in_date:
            raise BusinessLogicException(
                f"Booking {booking.id} is missing preferred_check_in_date"
            )

    def _build_availability_request(self, booking) -> RoomAvailabilityRequest:
        """Build availability request from booking data."""
        return RoomAvailabilityRequest(
            hostel_id=booking.hostel_id,
            check_in_date=booking.preferred_check_in_date,
            stay_duration_months=booking.stay_duration_months or 1,
            room_type=booking.room_type_requested,
        )

    def _select_best_room(
        self,
        available_rooms: List,
        booking,
        preferences: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Select the best room based on scoring algorithm.

        Scoring factors:
        - Match score (from availability check)
        - Number of available beds (prefer more options)
        - Price compatibility
        - Floor preference
        - Amenities match
        """
        scored_rooms = []
        
        for room in available_rooms:
            score = self._calculate_room_score(room, booking, preferences)
            scored_rooms.append({
                "room": room,
                "score": score,
            })
        
        # Sort by score (descending) and select best
        scored_rooms.sort(key=lambda x: x["score"], reverse=True)
        best = scored_rooms[0]
        
        return {
            "room_id": best["room"].room_id,
            "bed_id": best["room"].suggested_bed_id,
            "score": best["score"],
            "reasoning": self._generate_reasoning(best["room"], booking),
        }

    def _calculate_room_score(
        self,
        room,
        booking,
        preferences: Dict[str, Any],
    ) -> float:
        """
        Calculate comprehensive score for a room.

        Returns:
            float: Score between 0.0 and 1.0
        """
        score = 0.0
        max_score = 0.0
        
        # Base match score (weight: 0.4)
        if hasattr(room, 'match_score') and room.match_score is not None:
            score += float(room.match_score) * 0.4
        max_score += 0.4
        
        # Available beds factor (weight: 0.2)
        # More available beds = better (more flexibility)
        if hasattr(room, 'available_beds') and room.available_beds > 0:
            beds_score = min(room.available_beds / 4.0, 1.0)  # Normalize to max 4 beds
            score += beds_score * 0.2
        max_score += 0.2
        
        # Price compatibility (weight: 0.2)
        if (
            hasattr(room, 'price_per_bed')
            and hasattr(booking, 'budget_max')
            and booking.budget_max
        ):
            if room.price_per_bed <= booking.budget_max:
                price_ratio = 1.0 - (room.price_per_bed / booking.budget_max)
                score += price_ratio * 0.2
        max_score += 0.2
        
        # Floor preference (weight: 0.1)
        preferred_floor = preferences.get('preferred_floor')
        if preferred_floor and hasattr(room, 'floor_number'):
            if room.floor_number == preferred_floor:
                score += 0.1
        max_score += 0.1
        
        # Amenities match (weight: 0.1)
        # This can be enhanced based on available amenity data
        max_score += 0.1
        
        # Normalize score
        if max_score > 0:
            return score / max_score
        
        return 0.5  # Default moderate score

    def _generate_reasoning(self, room, booking) -> str:
        """Generate human-readable reasoning for allocation choice."""
        reasons = []
        
        if hasattr(room, 'match_score') and room.match_score:
            reasons.append(f"Match score: {room.match_score:.2f}")
        
        if hasattr(room, 'available_beds'):
            reasons.append(f"{room.available_beds} beds available")
        
        if hasattr(room, 'price_per_bed'):
            reasons.append(f"Price: {room.price_per_bed}")
        
        return ", ".join(reasons) if reasons else "Best available option"