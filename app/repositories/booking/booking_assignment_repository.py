# app/repositories/booking/booking_assignment_repository.py
"""
Booking assignment repository for room and bed assignment management.

Provides intelligent assignment operations, conflict resolution,
assignment tracking, and optimization.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import EntityNotFoundError, ValidationError
from app.models.booking.booking_assignment import (
    AssignmentHistory,
    BookingAssignment,
)
from app.models.booking.booking import Booking
from app.models.room.room import Room
from app.models.room.bed import Bed
from app.models.base.enums import BedStatus, RoomStatus
from app.repositories.base.base_repository import (
    AuditContext,
    BaseRepository,
    QueryOptions,
)


class BookingAssignmentRepository(BaseRepository[BookingAssignment]):
    """
    Repository for booking assignment operations.
    
    Provides:
    - Room and bed assignment
    - Assignment conflict detection
    - Assignment optimization
    - Assignment history tracking
    - Availability checking
    """
    
    def __init__(self, session: Session):
        """Initialize assignment repository."""
        super().__init__(session, BookingAssignment)
    
    # ==================== ASSIGNMENT OPERATIONS ====================
    
    def create_assignment(
        self,
        assignment_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingAssignment:
        """
        Create new booking assignment.
        
        Args:
            assignment_data: Assignment information
            audit_context: Audit context
            
        Returns:
            Created assignment
            
        Raises:
            ValidationError: If assignment conflicts or validation fails
        """
        booking_id = assignment_data.get('booking_id')
        room_id = assignment_data.get('room_id')
        bed_id = assignment_data.get('bed_id')
        
        # Validate no existing active assignment for booking
        existing = self.find_active_by_booking(booking_id)
        if existing:
            raise ValidationError(
                f"Booking {booking_id} already has an active assignment"
            )
        
        # Validate bed belongs to room
        bed = self.session.get(Bed, bed_id)
        if not bed or bed.room_id != room_id:
            raise ValidationError("Bed does not belong to the specified room")
        
        # Validate bed is available
        if bed.status != BedStatus.AVAILABLE:
            raise ValidationError(f"Bed {bed_id} is not available for assignment")
        
        # Create assignment
        assignment = BookingAssignment(
            assigned_by=audit_context.user_id if audit_context else None,
            assigned_at=datetime.utcnow(),
            **assignment_data,
        )
        
        created = self.create(assignment, audit_context)
        
        # Create history entry
        self._create_assignment_history(
            assignment_id=created.id,
            booking_id=booking_id,
            to_room_id=room_id,
            to_bed_id=bed_id,
            change_type="initial",
            changed_by=audit_context.user_id if audit_context else None,
            change_reason="Initial assignment",
        )
        
        # Update bed status
        bed.status = BedStatus.RESERVED
        self.session.flush()
        
        return created
    
    def find_by_booking(self, booking_id: UUID) -> Optional[BookingAssignment]:
        """
        Find assignment for a booking (including inactive).
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Assignment if found
        """
        query = select(BookingAssignment).where(
            BookingAssignment.booking_id == booking_id
        ).where(
            BookingAssignment.deleted_at.is_(None)
        ).options(
            joinedload(BookingAssignment.booking),
            joinedload(BookingAssignment.room),
            joinedload(BookingAssignment.bed),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def find_active_by_booking(self, booking_id: UUID) -> Optional[BookingAssignment]:
        """
        Find active assignment for a booking.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Active assignment if found
        """
        query = select(BookingAssignment).where(
            and_(
                BookingAssignment.booking_id == booking_id,
                BookingAssignment.is_active == True,
                BookingAssignment.deleted_at.is_(None),
            )
        ).options(
            joinedload(BookingAssignment.booking),
            joinedload(BookingAssignment.room),
            joinedload(BookingAssignment.bed),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def find_by_room(
        self,
        room_id: UUID,
        active_only: bool = True,
    ) -> List[BookingAssignment]:
        """
        Find assignments for a room.
        
        Args:
            room_id: Room UUID
            active_only: If True, only return active assignments
            
        Returns:
            List of assignments
        """
        query = select(BookingAssignment).where(
            and_(
                BookingAssignment.room_id == room_id,
                BookingAssignment.deleted_at.is_(None),
            )
        )
        
        if active_only:
            query = query.where(BookingAssignment.is_active == True)
        
        query = query.options(
            joinedload(BookingAssignment.booking),
            joinedload(BookingAssignment.bed),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_by_bed(
        self,
        bed_id: UUID,
        active_only: bool = True,
    ) -> List[BookingAssignment]:
        """
        Find assignments for a bed.
        
        Args:
            bed_id: Bed UUID
            active_only: If True, only return active assignments
            
        Returns:
            List of assignments
        """
        query = select(BookingAssignment).where(
            and_(
                BookingAssignment.bed_id == bed_id,
                BookingAssignment.deleted_at.is_(None),
            )
        )
        
        if active_only:
            query = query.where(BookingAssignment.is_active == True)
        
        query = query.options(
            joinedload(BookingAssignment.booking),
            joinedload(BookingAssignment.room),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def reassign_booking(
        self,
        booking_id: UUID,
        new_room_id: UUID,
        new_bed_id: UUID,
        reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingAssignment:
        """
        Reassign booking to different room/bed.
        
        Args:
            booking_id: Booking UUID
            new_room_id: New room UUID
            new_bed_id: New bed UUID
            reason: Reassignment reason
            audit_context: Audit context
            
        Returns:
            Updated assignment
            
        Raises:
            EntityNotFoundError: If assignment not found
            ValidationError: If reassignment validation fails
        """
        assignment = self.find_active_by_booking(booking_id)
        if not assignment:
            raise EntityNotFoundError(
                f"Active assignment for booking {booking_id} not found"
            )
        
        # Validate new bed belongs to new room
        new_bed = self.session.get(Bed, new_bed_id)
        if not new_bed or new_bed.room_id != new_room_id:
            raise ValidationError("Bed does not belong to the specified room")
        
        # Validate new bed is available
        if new_bed.status not in [BedStatus.AVAILABLE, BedStatus.RESERVED]:
            raise ValidationError(f"Bed {new_bed_id} is not available")
        
        # Store old assignment info
        old_room_id = assignment.room_id
        old_bed_id = assignment.bed_id
        old_bed = self.session.get(Bed, old_bed_id)
        
        # Update assignment
        assignment.room_id = new_room_id
        assignment.bed_id = new_bed_id
        
        self.session.flush()
        
        # Create history entry
        self._create_assignment_history(
            assignment_id=assignment.id,
            booking_id=booking_id,
            from_room_id=old_room_id,
            from_bed_id=old_bed_id,
            to_room_id=new_room_id,
            to_bed_id=new_bed_id,
            change_type="reassignment",
            changed_by=audit_context.user_id if audit_context else None,
            change_reason=reason,
        )
        
        # Update bed statuses
        if old_bed:
            old_bed.status = BedStatus.AVAILABLE
        new_bed.status = BedStatus.RESERVED
        
        self.session.flush()
        self.session.refresh(assignment)
        
        return assignment
    
    def deactivate_assignment(
        self,
        booking_id: UUID,
        reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingAssignment:
        """
        Deactivate booking assignment.
        
        Args:
            booking_id: Booking UUID
            reason: Deactivation reason
            audit_context: Audit context
            
        Returns:
            Deactivated assignment
        """
        assignment = self.find_active_by_booking(booking_id)
        if not assignment:
            raise EntityNotFoundError(
                f"Active assignment for booking {booking_id} not found"
            )
        
        # Deactivate
        assignment.deactivate(
            deactivated_by=audit_context.user_id if audit_context else None,
            reason=reason,
        )
        
        # Update bed status
        bed = self.session.get(Bed, assignment.bed_id)
        if bed:
            bed.status = BedStatus.AVAILABLE
        
        self.session.flush()
        self.session.refresh(assignment)
        
        return assignment
    
    def reactivate_assignment(
        self,
        booking_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingAssignment:
        """
        Reactivate deactivated assignment.
        
        Args:
            booking_id: Booking UUID
            audit_context: Audit context
            
        Returns:
            Reactivated assignment
        """
        assignment = self.find_by_booking(booking_id)
        if not assignment:
            raise EntityNotFoundError(f"Assignment for booking {booking_id} not found")
        
        if assignment.is_active:
            raise ValidationError("Assignment is already active")
        
        # Validate bed is available
        bed = self.session.get(Bed, assignment.bed_id)
        if not bed or bed.status not in [BedStatus.AVAILABLE, BedStatus.RESERVED]:
            raise ValidationError("Bed is no longer available")
        
        # Reactivate
        assignment.reactivate()
        
        # Update bed status
        bed.status = BedStatus.RESERVED
        
        self.session.flush()
        self.session.refresh(assignment)
        
        return assignment
    
    # ==================== ASSIGNMENT HISTORY ====================
    
    def _create_assignment_history(
        self,
        assignment_id: UUID,
        booking_id: UUID,
        to_room_id: UUID,
        to_bed_id: UUID,
        change_type: str,
        changed_by: Optional[UUID],
        change_reason: str,
        from_room_id: Optional[UUID] = None,
        from_bed_id: Optional[UUID] = None,
    ) -> AssignmentHistory:
        """Create assignment history entry."""
        history = AssignmentHistory(
            assignment_id=assignment_id,
            booking_id=booking_id,
            from_room_id=from_room_id,
            from_bed_id=from_bed_id,
            to_room_id=to_room_id,
            to_bed_id=to_bed_id,
            change_type=change_type,
            changed_by=changed_by,
            change_reason=change_reason,
            changed_at=datetime.utcnow(),
        )
        
        self.session.add(history)
        self.session.flush()
        
        return history
    
    def get_assignment_history(self, booking_id: UUID) -> List[AssignmentHistory]:
        """
        Get assignment history for a booking.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            List of assignment changes
        """
        query = select(AssignmentHistory).where(
            AssignmentHistory.booking_id == booking_id
        ).order_by(
            AssignmentHistory.changed_at.desc()
        ).options(
            joinedload(AssignmentHistory.from_room),
            joinedload(AssignmentHistory.from_bed),
            joinedload(AssignmentHistory.to_room),
            joinedload(AssignmentHistory.to_bed),
            joinedload(AssignmentHistory.changer),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    # ==================== AVAILABILITY & OPTIMIZATION ====================
    
    def find_available_beds_for_booking(
        self,
        hostel_id: UUID,
        room_type: str,
        gender_preference: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Bed]:
        """
        Find available beds suitable for a booking.
        
        Args:
            hostel_id: Hostel UUID
            room_type: Requested room type
            gender_preference: Optional gender preference
            limit: Optional result limit
            
        Returns:
            List of available beds
        """
        query = select(Bed).join(
            Room,
            Bed.room_id == Room.id
        ).where(
            and_(
                Room.hostel_id == hostel_id,
                Room.room_type == room_type,
                Bed.status == BedStatus.AVAILABLE,
                Room.status == RoomStatus.AVAILABLE,
                Bed.deleted_at.is_(None),
                Room.deleted_at.is_(None),
            )
        )
        
        if gender_preference:
            query = query.where(Room.gender_type == gender_preference)
        
        query = query.options(
            joinedload(Bed.room)
        ).order_by(
            Room.floor_number.asc(),
            Room.room_number.asc(),
            Bed.bed_number.asc(),
        )
        
        if limit:
            query = query.limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_room_assignment_statistics(
        self,
        room_id: UUID,
    ) -> Dict[str, any]:
        """
        Get assignment statistics for a room.
        
        Args:
            room_id: Room UUID
            
        Returns:
            Statistics dictionary
        """
        assignments = self.find_by_room(room_id, active_only=True)
        
        room = self.session.get(Room, room_id)
        if not room:
            raise EntityNotFoundError(f"Room {room_id} not found")
        
        total_beds = room.capacity
        assigned_beds = len(assignments)
        available_beds = total_beds - assigned_beds
        occupancy_rate = (assigned_beds / total_beds * 100) if total_beds > 0 else 0
        
        return {
            "room_id": room_id,
            "total_beds": total_beds,
            "assigned_beds": assigned_beds,
            "available_beds": available_beds,
            "occupancy_rate": occupancy_rate,
            "assignments": assignments,
        }
    
    def find_auto_assigned(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[BookingAssignment]:
        """
        Find auto-assigned bookings.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            List of auto-assigned bookings
        """
        query = select(BookingAssignment).join(
            Booking,
            BookingAssignment.booking_id == Booking.id
        ).where(
            and_(
                BookingAssignment.auto_assigned == True,
                BookingAssignment.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(BookingAssignment.assigned_at >= date_from)
        
        if date_to:
            query = query.where(BookingAssignment.assigned_at <= date_to)
        
        query = query.order_by(BookingAssignment.assigned_at.desc()).options(
            joinedload(BookingAssignment.booking),
            joinedload(BookingAssignment.room),
            joinedload(BookingAssignment.bed),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())