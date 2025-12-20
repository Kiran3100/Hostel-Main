# app/services/booking/booking_assignment_service.py
"""
Booking assignment service for room and bed assignment management.

Handles intelligent room/bed assignment, conflict detection, reassignment,
and assignment optimization.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ValidationError,
)
from app.models.base.enums import BedStatus, BookingStatus, RoomStatus
from app.repositories.booking.booking_repository import BookingRepository
from app.repositories.booking.booking_assignment_repository import (
    BookingAssignmentRepository,
)
from app.repositories.base.base_repository import AuditContext


class BookingAssignmentService:
    """
    Service for booking room and bed assignment management.
    
    Responsibilities:
    - Intelligent room/bed assignment
    - Assignment conflict detection and resolution
    - Manual and automatic assignment
    - Reassignment workflow
    - Assignment optimization
    - Availability tracking
    """
    
    def __init__(
        self,
        session: Session,
        booking_repo: Optional[BookingRepository] = None,
        assignment_repo: Optional[BookingAssignmentRepository] = None,
    ):
        """Initialize assignment service."""
        self.session = session
        self.booking_repo = booking_repo or BookingRepository(session)
        self.assignment_repo = assignment_repo or BookingAssignmentRepository(session)
    
    # ==================== ASSIGNMENT OPERATIONS ====================
    
    def assign_room_and_bed(
        self,
        booking_id: UUID,
        room_id: UUID,
        bed_id: UUID,
        assigned_by_id: UUID,
        assignment_notes: Optional[str] = None,
        override_check_in_date: Optional[datetime] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Manually assign room and bed to a booking.
        
        Args:
            booking_id: Booking UUID
            room_id: Room UUID
            bed_id: Bed UUID
            assigned_by_id: Admin UUID
            assignment_notes: Notes about assignment
            override_check_in_date: Override check-in date
            audit_context: Audit context
            
        Returns:
            Assignment dictionary
            
        Raises:
            EntityNotFoundError: If booking not found
            BusinessRuleViolationError: If assignment invalid
            ValidationError: If validation fails
        """
        # Validate booking
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        # Check booking status
        if booking.booking_status not in [
            BookingStatus.APPROVED,
            BookingStatus.CONFIRMED,
        ]:
            raise BusinessRuleViolationError(
                "Only approved or confirmed bookings can be assigned"
            )
        
        # Check for existing assignment
        existing = self.assignment_repo.find_active_by_booking(booking_id)
        if existing:
            raise BusinessRuleViolationError(
                "Booking already has an active assignment. Use reassign instead."
            )
        
        # Create assignment
        assignment_data = {
            "booking_id": booking_id,
            "room_id": room_id,
            "bed_id": bed_id,
            "assigned_by": assigned_by_id,
            "assignment_notes": assignment_notes,
            "override_check_in_date": override_check_in_date,
            "auto_assigned": False,
        }
        
        assignment = self.assignment_repo.create_assignment(
            assignment_data, audit_context
        )
        
        return self._assignment_to_dict(assignment)
    
    def auto_assign_room_and_bed(
        self,
        booking_id: UUID,
        gender_preference: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Automatically assign best available room and bed.
        
        Args:
            booking_id: Booking UUID
            gender_preference: Gender preference for room
            audit_context: Audit context
            
        Returns:
            Assignment dictionary
            
        Raises:
            BusinessRuleViolationError: If no suitable assignment found
        """
        # Get booking
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        # Find available beds
        available_beds = self.assignment_repo.find_available_beds_for_booking(
            booking.hostel_id,
            str(booking.room_type_requested),
            gender_preference,
            limit=1,
        )
        
        if not available_beds:
            raise BusinessRuleViolationError(
                "No available beds found for automatic assignment"
            )
        
        # Assign first available
        bed = available_beds[0]
        
        assignment_data = {
            "booking_id": booking_id,
            "room_id": bed.room_id,
            "bed_id": bed.id,
            "assignment_notes": "Automatically assigned",
            "auto_assigned": True,
        }
        
        assignment = self.assignment_repo.create_assignment(
            assignment_data, audit_context
        )
        
        return self._assignment_to_dict(assignment)
    
    def reassign_booking(
        self,
        booking_id: UUID,
        new_room_id: UUID,
        new_bed_id: UUID,
        reassigned_by_id: UUID,
        reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Reassign booking to different room/bed.
        
        Args:
            booking_id: Booking UUID
            new_room_id: New room UUID
            new_bed_id: New bed UUID
            reassigned_by_id: Admin UUID
            reason: Reassignment reason
            audit_context: Audit context
            
        Returns:
            Updated assignment dictionary
        """
        assignment = self.assignment_repo.reassign_booking(
            booking_id, new_room_id, new_bed_id, reason, audit_context
        )
        
        return self._assignment_to_dict(assignment)
    
    def deactivate_assignment(
        self,
        booking_id: UUID,
        deactivated_by_id: UUID,
        reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Deactivate a booking assignment.
        
        Args:
            booking_id: Booking UUID
            deactivated_by_id: Admin UUID
            reason: Deactivation reason
            audit_context: Audit context
            
        Returns:
            Deactivated assignment dictionary
        """
        assignment = self.assignment_repo.deactivate_assignment(
            booking_id, reason, audit_context
        )
        
        return self._assignment_to_dict(assignment)
    
    def reactivate_assignment(
        self,
        booking_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Reactivate a deactivated assignment.
        
        Args:
            booking_id: Booking UUID
            audit_context: Audit context
            
        Returns:
            Reactivated assignment dictionary
        """
        assignment = self.assignment_repo.reactivate_assignment(
            booking_id, audit_context
        )
        
        return self._assignment_to_dict(assignment)
    
    # ==================== ASSIGNMENT QUERIES ====================
    
    def get_booking_assignment(
        self,
        booking_id: UUID,
        include_history: bool = False,
    ) -> Optional[Dict]:
        """
        Get assignment for a booking.
        
        Args:
            booking_id: Booking UUID
            include_history: Include assignment history
            
        Returns:
            Assignment dictionary with optional history
        """
        assignment = self.assignment_repo.find_by_booking(booking_id)
        if not assignment:
            return None
        
        result = self._assignment_to_dict(assignment)
        
        if include_history:
            history = self.assignment_repo.get_assignment_history(booking_id)
            result["history"] = [self._history_to_dict(h) for h in history]
        
        return result
    
    def get_room_assignments(
        self,
        room_id: UUID,
        active_only: bool = True,
    ) -> List[Dict]:
        """Get all assignments for a room."""
        assignments = self.assignment_repo.find_by_room(room_id, active_only)
        return [self._assignment_to_dict(a) for a in assignments]
    
    def get_bed_assignments(
        self,
        bed_id: UUID,
        active_only: bool = True,
    ) -> List[Dict]:
        """Get all assignments for a bed."""
        assignments = self.assignment_repo.find_by_bed(bed_id, active_only)
        return [self._assignment_to_dict(a) for a in assignments]
    
    # ==================== AVAILABILITY & OPTIMIZATION ====================
    
    def find_available_beds(
        self,
        hostel_id: UUID,
        room_type: str,
        gender_preference: Optional[str] = None,
        limit: Optional[int] = 10,
    ) -> List[Dict]:
        """
        Find available beds for assignment.
        
        Args:
            hostel_id: Hostel UUID
            room_type: Room type
            gender_preference: Gender preference
            limit: Result limit
            
        Returns:
            List of available bed dictionaries
        """
        beds = self.assignment_repo.find_available_beds_for_booking(
            hostel_id, room_type, gender_preference, limit
        )
        
        return [
            {
                "bed_id": str(bed.id),
                "bed_number": bed.bed_number,
                "room_id": str(bed.room_id),
                "room_number": bed.room.room_number,
                "floor_number": bed.room.floor_number,
                "room_type": bed.room.room_type.value,
            }
            for bed in beds
        ]
    
    def get_room_occupancy(self, room_id: UUID) -> Dict:
        """
        Get occupancy statistics for a room.
        
        Args:
            room_id: Room UUID
            
        Returns:
            Occupancy statistics dictionary
        """
        return self.assignment_repo.get_room_assignment_statistics(room_id)
    
    def get_auto_assigned_bookings(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict]:
        """Get auto-assigned bookings."""
        assignments = self.assignment_repo.find_auto_assigned(
            hostel_id, date_from, date_to
        )
        return [self._assignment_to_dict(a) for a in assignments]
    
    # ==================== BULK OPERATIONS ====================
    
    def bulk_assign_bookings(
        self,
        booking_assignments: List[Dict],
        assigned_by_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Assign multiple bookings in bulk.
        
        Args:
            booking_assignments: List of {booking_id, room_id, bed_id}
            assigned_by_id: Admin UUID
            audit_context: Audit context
            
        Returns:
            Summary of bulk assignment
        """
        successful = []
        failed = []
        
        for assignment_data in booking_assignments:
            try:
                assignment = self.assign_room_and_bed(
                    booking_id=assignment_data["booking_id"],
                    room_id=assignment_data["room_id"],
                    bed_id=assignment_data["bed_id"],
                    assigned_by_id=assigned_by_id,
                    audit_context=audit_context,
                )
                successful.append(assignment)
            except Exception as e:
                failed.append(
                    {
                        "booking_id": str(assignment_data["booking_id"]),
                        "error": str(e),
                    }
                )
        
        return {
            "total": len(booking_assignments),
            "successful": len(successful),
            "failed": len(failed),
            "successful_assignments": successful,
            "failed_assignments": failed,
        }
    
    # ==================== HELPER METHODS ====================
    
    def _assignment_to_dict(self, assignment) -> Dict:
        """Convert assignment model to dictionary."""
        return {
            "id": str(assignment.id),
            "booking_id": str(assignment.booking_id),
            "room_id": str(assignment.room_id),
            "bed_id": str(assignment.bed_id),
            "assigned_by": (
                str(assignment.assigned_by) if assignment.assigned_by else None
            ),
            "assigned_at": assignment.assigned_at.isoformat(),
            "assignment_notes": assignment.assignment_notes,
            "auto_assigned": assignment.auto_assigned,
            "is_active": assignment.is_active,
            "override_check_in_date": (
                assignment.override_check_in_date.isoformat()
                if assignment.override_check_in_date
                else None
            ),
            "deactivated_at": (
                assignment.deactivated_at.isoformat()
                if assignment.deactivated_at
                else None
            ),
            "deactivation_reason": assignment.deactivation_reason,
        }
    
    def _history_to_dict(self, history) -> Dict:
        """Convert assignment history to dictionary."""
        return {
            "id": str(history.id),
            "from_room_id": str(history.from_room_id) if history.from_room_id else None,
            "from_bed_id": str(history.from_bed_id) if history.from_bed_id else None,
            "to_room_id": str(history.to_room_id),
            "to_bed_id": str(history.to_bed_id),
            "changed_at": history.changed_at.isoformat(),
            "change_type": history.change_type,
            "change_reason": history.change_reason,
            "is_initial_assignment": history.is_initial_assignment,
            "is_room_change": history.is_room_change,
            "is_bed_change": history.is_bed_change,
        }