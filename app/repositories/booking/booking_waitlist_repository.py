# app/repositories/booking/booking_modification_repository.py
"""
Booking modification repository for modification request management.

Provides modification request tracking, approval workflows, pricing impact
analysis, and modification history.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import EntityNotFoundError, ValidationError
from app.models.booking.booking_modification import (
    BookingModification,
    ModificationApprovalRecord,
)
from app.models.booking.booking import Booking
from app.models.base.enums import RoomType
from app.repositories.base.base_repository import (
    AuditContext,
    BaseRepository,
    QueryOptions,
)


class BookingModificationRepository(BaseRepository[BookingModification]):
    """
    Repository for booking modification operations.
    
    Provides:
    - Modification request management
    - Pricing impact calculation
    - Approval workflow tracking
    - Modification analytics
    - Application management
    """
    
    def __init__(self, session: Session):
        """Initialize modification repository."""
        super().__init__(session, BookingModification)
    
    # ==================== MODIFICATION OPERATIONS ====================
    
    def create_modification_request(
        self,
        booking_id: UUID,
        modification_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingModification:
        """
        Create modification request for a booking.
        
        Args:
            booking_id: Booking UUID
            modification_data: Modification information
            audit_context: Audit context
            
        Returns:
            Created modification request
            
        Raises:
            EntityNotFoundError: If booking not found
            ValidationError: If validation fails
        """
        # Get booking
        booking = self.session.get(Booking, booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        # Store original values
        if 'original_check_in_date' not in modification_data:
            modification_data['original_check_in_date'] = booking.preferred_check_in_date
        
        if 'original_duration_months' not in modification_data:
            modification_data['original_duration_months'] = booking.stay_duration_months
        
        if 'original_room_type' not in modification_data:
            modification_data['original_room_type'] = booking.room_type_requested
        
        if 'original_total_amount' not in modification_data:
            modification_data['original_total_amount'] = booking.total_amount
        
        # Determine modification type
        modification_types = []
        if modification_data.get('modify_check_in_date'):
            modification_types.append('date')
        if modification_data.get('modify_duration'):
            modification_types.append('duration')
        if modification_data.get('modify_room_type'):
            modification_types.append('room_type')
        
        if not modification_types:
            raise ValidationError("At least one modification type must be specified")
        
        modification_data['modification_type'] = (
            'multiple' if len(modification_types) > 1
            else modification_types[0]
        )
        
        modification = BookingModification(
            booking_id=booking_id,
            requested_by=audit_context.user_id if audit_context else None,
            requested_at=datetime.utcnow(),
            **modification_data,
        )
        
        return self.create(modification, audit_context)
    
    def find_by_booking(
        self,
        booking_id: UUID,
        status: Optional[str] = None,
    ) -> List[BookingModification]:
        """
        Find modification requests for a booking.
        
        Args:
            booking_id: Booking UUID
            status: Optional status filter
            
        Returns:
            List of modification requests
        """
        query = select(BookingModification).where(
            and_(
                BookingModification.booking_id == booking_id,
                BookingModification.deleted_at.is_(None),
            )
        )
        
        if status:
            query = query.where(BookingModification.modification_status == status)
        
        query = query.order_by(
            BookingModification.requested_at.desc()
        ).options(
            joinedload(BookingModification.booking),
            joinedload(BookingModification.requester),
            joinedload(BookingModification.approval_record),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_pending_modifications(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingModification]:
        """
        Find pending modification requests.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of pending modifications
        """
        query = select(BookingModification).join(
            Booking,
            BookingModification.booking_id == Booking.id
        ).where(
            and_(
                BookingModification.modification_status == 'pending',
                BookingModification.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.order_by(
            BookingModification.requested_at.asc()
        ).options(
            joinedload(BookingModification.booking),
            joinedload(BookingModification.requester),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def calculate_price_impact(
        self,
        modification_id: UUID,
        new_monthly_rent: Decimal,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingModification:
        """
        Calculate and update price impact of modification.
        
        Args:
            modification_id: Modification UUID
            new_monthly_rent: New monthly rent amount
            audit_context: Audit context
            
        Returns:
            Updated modification
        """
        modification = self.find_by_id(modification_id)
        if not modification:
            raise EntityNotFoundError(f"Modification {modification_id} not found")
        
        # Calculate price impact
        new_duration = (
            modification.new_duration_months
            if modification.modify_duration
            else modification.original_duration_months
        )
        
        modification.calculate_price_impact(new_monthly_rent, new_duration)
        
        self.session.flush()
        self.session.refresh(modification)
        
        return modification
    
    def approve_modification(
        self,
        modification_id: UUID,
        approved_by: UUID,
        approval_notes: Optional[str] = None,
        adjusted_price: Optional[Decimal] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingModification:
        """
        Approve modification request.
        
        Args:
            modification_id: Modification UUID
            approved_by: Admin UUID approving the modification
            approval_notes: Optional approval notes
            adjusted_price: Optional admin-adjusted price
            audit_context: Audit context
            
        Returns:
            Approved modification
        """
        modification = self.find_by_id(modification_id)
        if not modification:
            raise EntityNotFoundError(f"Modification {modification_id} not found")
        
        modification.approve(approved_by)
        
        # Create approval record
        approval_repo = ModificationApprovalRecordRepository(self.session)
        approval_repo.create_approval_record(
            modification_id=modification_id,
            approved=True,
            approved_by=approved_by,
            admin_notes=approval_notes,
            adjusted_price=adjusted_price,
            audit_context=audit_context,
        )
        
        self.session.flush()
        self.session.refresh(modification)
        
        return modification
    
    def reject_modification(
        self,
        modification_id: UUID,
        rejected_by: UUID,
        reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingModification:
        """
        Reject modification request.
        
        Args:
            modification_id: Modification UUID
            rejected_by: Admin UUID rejecting the modification
            reason: Rejection reason
            audit_context: Audit context
            
        Returns:
            Rejected modification
        """
        modification = self.find_by_id(modification_id)
        if not modification:
            raise EntityNotFoundError(f"Modification {modification_id} not found")
        
        modification.reject(rejected_by, reason)
        
        # Create approval record
        approval_repo = ModificationApprovalRecordRepository(self.session)
        approval_repo.create_approval_record(
            modification_id=modification_id,
            approved=False,
            approved_by=rejected_by,
            admin_notes=reason,
            audit_context=audit_context,
        )
        
        self.session.flush()
        self.session.refresh(modification)
        
        return modification
    
    def apply_modification(
        self,
        modification_id: UUID,
        applied_by: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Tuple[BookingModification, Booking]:
        """
        Apply approved modification to booking.
        
        Args:
            modification_id: Modification UUID
            applied_by: Admin UUID applying the modification
            audit_context: Audit context
            
        Returns:
            Tuple of (modification, updated_booking)
            
        Raises:
            ValidationError: If modification cannot be applied
        """
        modification = self.find_by_id(modification_id)
        if not modification:
            raise EntityNotFoundError(f"Modification {modification_id} not found")
        
        if modification.modification_status != 'approved':
            raise ValidationError("Only approved modifications can be applied")
        
        booking = modification.booking
        
        # Apply changes
        if modification.modify_check_in_date and modification.new_check_in_date:
            booking.preferred_check_in_date = modification.new_check_in_date
        
        if modification.modify_duration and modification.new_duration_months:
            booking.stay_duration_months = modification.new_duration_months
        
        if modification.modify_room_type and modification.new_room_type:
            booking.room_type_requested = modification.new_room_type
        
        # Update pricing if changed
        if modification.new_total_amount:
            booking.total_amount = modification.new_total_amount
        
        # Mark modification as applied
        modification.apply_modification(applied_by)
        
        self.session.flush()
        self.session.refresh(modification)
        self.session.refresh(booking)
        
        return modification, booking
    
    def find_by_type(
        self,
        modification_type: str,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[BookingModification]:
        """
        Find modifications by type.
        
        Args:
            modification_type: Type of modification
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            List of modifications
        """
        query = select(BookingModification).join(
            Booking,
            BookingModification.booking_id == Booking.id
        ).where(
            and_(
                BookingModification.modification_type == modification_type,
                BookingModification.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(BookingModification.requested_at >= date_from)
        
        if date_to:
            query = query.where(BookingModification.requested_at <= date_to)
        
        query = query.order_by(
            BookingModification.requested_at.desc()
        ).options(
            joinedload(BookingModification.booking),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_with_price_increase(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingModification]:
        """
        Find modifications that result in price increase.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of modifications with price increase
        """
        query = select(BookingModification).join(
            Booking,
            BookingModification.booking_id == Booking.id
        ).where(
            BookingModification.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        modifications = self.session.execute(query).scalars().all()
        
        # Filter for price increases
        with_increase = [m for m in modifications if m.has_price_increase]
        
        return with_increase
    
    def get_modification_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Get modification statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics dictionary
        """
        query = select(BookingModification).join(
            Booking,
            BookingModification.booking_id == Booking.id
        ).where(
            BookingModification.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(BookingModification.requested_at >= date_from)
        
        if date_to:
            query = query.where(BookingModification.requested_at <= date_to)
        
        modifications = self.session.execute(query).scalars().all()
        
        total_modifications = len(modifications)
        
        # Count by status
        pending = sum(1 for m in modifications if m.is_pending)
        approved = sum(1 for m in modifications if m.is_approved)
        applied = sum(1 for m in modifications if m.is_applied)
        rejected = sum(1 for m in modifications if m.modification_status == 'rejected')
        
        # Count by type
        by_type = {}
        for mod in modifications:
            by_type[mod.modification_type] = by_type.get(mod.modification_type, 0) + 1
        
        # Price impact
        with_price_increase = sum(1 for m in modifications if m.has_price_increase)
        with_price_decrease = sum(1 for m in modifications if m.has_price_decrease)
        
        avg_price_change = (
            sum(m.price_difference for m in modifications if m.price_difference)
            / total_modifications
            if total_modifications > 0 else Decimal("0.00")
        )
        
        # Acceptance metrics
        total_decided = approved + rejected
        approval_rate = (approved / total_decided * 100) if total_decided > 0 else 0
        application_rate = (applied / approved * 100) if approved > 0 else 0
        
        return {
            "total_modifications": total_modifications,
            "pending_modifications": pending,
            "approved_modifications": approved,
            "applied_modifications": applied,
            "rejected_modifications": rejected,
            "approval_rate": approval_rate,
            "application_rate": application_rate,
            "modifications_by_type": by_type,
            "with_price_increase": with_price_increase,
            "with_price_decrease": with_price_decrease,
            "average_price_change": avg_price_change,
        }


class ModificationApprovalRecordRepository(BaseRepository[ModificationApprovalRecord]):
    """Repository for modification approval record management."""
    
    def __init__(self, session: Session):
        """Initialize approval record repository."""
        super().__init__(session, ModificationApprovalRecord)
    
    def create_approval_record(
        self,
        modification_id: UUID,
        approved: bool,
        approved_by: UUID,
        admin_notes: Optional[str] = None,
        adjusted_price: Optional[Decimal] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> ModificationApprovalRecord:
        """
        Create approval record.
        
        Args:
            modification_id: Modification UUID
            approved: Whether approved or rejected
            approved_by: Admin making decision
            admin_notes: Optional notes
            adjusted_price: Optional adjusted price
            audit_context: Audit context
            
        Returns:
            Created approval record
        """
        record = ModificationApprovalRecord(
            modification_id=modification_id,
            approved=approved,
            decision_made_by=approved_by,
            admin_notes=admin_notes,
            adjusted_price=adjusted_price,
            approval_decision_at=datetime.utcnow(),
        )
        
        return self.create(record, audit_context)
    
    def find_by_modification(
        self,
        modification_id: UUID,
    ) -> Optional[ModificationApprovalRecord]:
        """
        Find approval record for a modification.
        
        Args:
            modification_id: Modification UUID
            
        Returns:
            Approval record if found
        """
        query = select(ModificationApprovalRecord).where(
            ModificationApprovalRecord.modification_id == modification_id
        ).options(
            joinedload(ModificationApprovalRecord.modification),
            joinedload(ModificationApprovalRecord.decision_maker),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()


# app/repositories/booking/booking_waitlist_repository.py
"""
Booking waitlist repository for waitlist management.

Provides waitlist entry management, priority tracking, notification handling,
and conversion to bookings.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import EntityNotFoundError, ValidationError
from app.models.booking.booking_waitlist import (
    BookingWaitlist,
    WaitlistNotification,
)
from app.models.base.enums import RoomType, WaitlistStatus
from app.repositories.base.base_repository import (
    AuditContext,
    BaseRepository,
    QueryOptions,
)


class BookingWaitlistRepository(BaseRepository[BookingWaitlist]):
    """
    Repository for booking waitlist operations.
    
    Provides:
    - Waitlist entry management
    - Priority queue management
    - Notification tracking
    - Conversion to bookings
    - Waitlist analytics
    """
    
    def __init__(self, session: Session):
        """Initialize waitlist repository."""
        super().__init__(session, BookingWaitlist)
    
    # ==================== WAITLIST OPERATIONS ====================
    
    def add_to_waitlist(
        self,
        waitlist_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingWaitlist:
        """
        Add entry to waitlist.
        
        Args:
            waitlist_data: Waitlist information
            audit_context: Audit context
            
        Returns:
            Created waitlist entry
        """
        # Calculate priority (next in line)
        hostel_id = waitlist_data.get('hostel_id')
        room_type = waitlist_data.get('room_type')
        
        max_priority = self.session.execute(
            select(func.max(BookingWaitlist.priority)).where(
                and_(
                    BookingWaitlist.hostel_id == hostel_id,
                    BookingWaitlist.room_type == room_type,
                    BookingWaitlist.status == WaitlistStatus.WAITING,
                    BookingWaitlist.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        
        next_priority = (max_priority or 0) + 1
        
        waitlist_entry = BookingWaitlist(
            priority=next_priority,
            status=WaitlistStatus.WAITING,
            **waitlist_data,
        )
        
        # Set default expiry (30 days)
        if not waitlist_entry.expires_at:
            waitlist_entry.expires_at = datetime.utcnow() + timedelta(days=30)
        
        return self.create(waitlist_entry, audit_context)
    
    def find_by_hostel_and_room_type(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        status: Optional[WaitlistStatus] = None,
        active_only: bool = True,
    ) -> List[BookingWaitlist]:
        """
        Find waitlist entries for hostel and room type.
        
        Args:
            hostel_id: Hostel UUID
            room_type: Room type
            status: Optional status filter
            active_only: If True, only return active entries
            
        Returns:
            List of waitlist entries ordered by priority
        """
        query = select(BookingWaitlist).where(
            and_(
                BookingWaitlist.hostel_id == hostel_id,
                BookingWaitlist.room_type == room_type,
                BookingWaitlist.deleted_at.is_(None),
            )
        )
        
        if status:
            query = query.where(BookingWaitlist.status == status)
        elif active_only:
            query = query.where(BookingWaitlist.status == WaitlistStatus.WAITING)
        
        query = query.order_by(
            BookingWaitlist.priority.asc()
        ).options(
            joinedload(BookingWaitlist.visitor),
            joinedload(BookingWaitlist.hostel),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_by_visitor(
        self,
        visitor_id: UUID,
        active_only: bool = True,
    ) -> List[BookingWaitlist]:
        """
        Find waitlist entries for a visitor.
        
        Args:
            visitor_id: Visitor UUID
            active_only: If True, only return active entries
            
        Returns:
            List of visitor's waitlist entries
        """
        query = select(BookingWaitlist).where(
            and_(
                BookingWaitlist.visitor_id == visitor_id,
                BookingWaitlist.deleted_at.is_(None),
            )
        )
        
        if active_only:
            query = query.where(BookingWaitlist.status == WaitlistStatus.WAITING)
        
        query = query.order_by(
            BookingWaitlist.created_at.desc()
        ).options(
            joinedload(BookingWaitlist.hostel),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_next_in_line(
        self,
        hostel_id: UUID,
        room_type: RoomType,
    ) -> Optional[BookingWaitlist]:
        """
        Get next visitor in line for waitlist.
        
        Args:
            hostel_id: Hostel UUID
            room_type: Room type
            
        Returns:
            Top priority waitlist entry
        """
        query = select(BookingWaitlist).where(
            and_(
                BookingWaitlist.hostel_id == hostel_id,
                BookingWaitlist.room_type == room_type,
                BookingWaitlist.status == WaitlistStatus.WAITING,
                BookingWaitlist.deleted_at.is_(None),
            )
        ).order_by(
            BookingWaitlist.priority.asc()
        ).limit(1).options(
            joinedload(BookingWaitlist.visitor),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def notify_availability(
        self,
        waitlist_id: UUID,
        room_id: UUID,
        bed_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Tuple[BookingWaitlist, WaitlistNotification]:
        """
        Notify waitlist entry about availability.
        
        Args:
            waitlist_id: Waitlist UUID
            room_id: Available room UUID
            bed_id: Available bed UUID
            audit_context: Audit context
            
        Returns:
            Tuple of (waitlist_entry, notification)
        """
        waitlist_entry = self.find_by_id(waitlist_id)
        if not waitlist_entry:
            raise EntityNotFoundError(f"Waitlist entry {waitlist_id} not found")
        
        # Create notification using waitlist method
        notification = waitlist_entry.notify_availability(room_id, bed_id)
        
        # Add notification to session
        self.session.add(notification)
        self.session.flush()
        self.session.refresh(waitlist_entry)
        self.session.refresh(notification)
        
        return waitlist_entry, notification
    
    def convert_to_booking(
        self,
        waitlist_id: UUID,
        booking_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingWaitlist:
        """
        Convert waitlist entry to booking.
        
        Args:
            waitlist_id: Waitlist UUID
            booking_id: Created booking UUID
            audit_context: Audit context
            
        Returns:
            Updated waitlist entry
        """
        waitlist_entry = self.find_by_id(waitlist_id)
        if not waitlist_entry:
            raise EntityNotFoundError(f"Waitlist entry {waitlist_id} not found")
        
        waitlist_entry.convert_to_booking(booking_id)
        
        # Reorder remaining waitlist entries
        self._reorder_priorities(
            waitlist_entry.hostel_id,
            waitlist_entry.room_type,
        )
        
        self.session.flush()
        self.session.refresh(waitlist_entry)
        
        return waitlist_entry
    
    def cancel_waitlist_entry(
        self,
        waitlist_id: UUID,
        reason: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingWaitlist:
        """
        Cancel waitlist entry.
        
        Args:
            waitlist_id: Waitlist UUID
            reason: Optional cancellation reason
            audit_context: Audit context
            
        Returns:
            Cancelled waitlist entry
        """
        waitlist_entry = self.find_by_id(waitlist_id)
        if not waitlist_entry:
            raise EntityNotFoundError(f"Waitlist entry {waitlist_id} not found")
        
        waitlist_entry.cancel(reason)
        
        # Reorder remaining entries
        self._reorder_priorities(
            waitlist_entry.hostel_id,
            waitlist_entry.room_type,
        )
        
        self.session.flush()
        self.session.refresh(waitlist_entry)
        
        return waitlist_entry
    
    def _reorder_priorities(
        self,
        hostel_id: UUID,
        room_type: RoomType,
    ) -> None:
        """Reorder priorities after entry removal."""
        waiting_entries = self.find_by_hostel_and_room_type(
            hostel_id,
            room_type,
            status=WaitlistStatus.WAITING,
        )
        
        for index, entry in enumerate(waiting_entries, start=1):
            if entry.priority != index:
                entry.update_priority(index)
        
        self.session.flush()
    
    def expire_old_entries(
        self,
        audit_context: Optional[AuditContext] = None,
    ) -> int:
        """
        Expire waitlist entries past their expiry date.
        
        Args:
            audit_context: Audit context
            
        Returns:
            Number of expired entries
        """
        query = select(BookingWaitlist).where(
            and_(
                BookingWaitlist.status == WaitlistStatus.WAITING,
                BookingWaitlist.expires_at.isnot(None),
                BookingWaitlist.expires_at <= datetime.utcnow(),
                BookingWaitlist.deleted_at.is_(None),
            )
        )
        
        expired_entries = self.session.execute(query).scalars().all()
        count = 0
        
        for entry in expired_entries:
            entry.mark_expired()
            count += 1
        
        if count > 0:
            self.session.flush()
        
        return count
    
    def find_expiring_soon(
        self,
        within_hours: int = 24,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingWaitlist]:
        """
        Find waitlist entries expiring soon.
        
        Args:
            within_hours: Hours threshold
            hostel_id: Optional hostel filter
            
        Returns:
            List of expiring entries
        """
        expiry_threshold = datetime.utcnow() + timedelta(hours=within_hours)
        
        query = select(BookingWaitlist).where(
            and_(
                BookingWaitlist.status == WaitlistStatus.WAITING,
                BookingWaitlist.expires_at.isnot(None),
                BookingWaitlist.expires_at <= expiry_threshold,
                BookingWaitlist.expires_at > datetime.utcnow(),
                BookingWaitlist.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(BookingWaitlist.hostel_id == hostel_id)
        
        query = query.order_by(
            BookingWaitlist.expires_at.asc()
        ).options(
            joinedload(BookingWaitlist.visitor),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_waitlist_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Get waitlist statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics dictionary
        """
        query = select(BookingWaitlist).where(
            BookingWaitlist.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(BookingWaitlist.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(BookingWaitlist.created_at >= date_from)
        
        if date_to:
            query = query.where(BookingWaitlist.created_at <= date_to)
        
        entries = self.session.execute(query).scalars().all()
        
        total_entries = len(entries)
        
        # Count by status
        by_status = {}
        for status in WaitlistStatus:
            count = sum(1 for e in entries if e.status == status)
            by_status[status.value] = count
        
        # Count by room type
        by_room_type = {}
        for entry in entries:
            room_type = str(entry.room_type)
            by_room_type[room_type] = by_room_type.get(room_type, 0) + 1
        
        # Conversion metrics
        converted = sum(1 for e in entries if e.converted_to_booking)
        conversion_rate = (converted / total_entries * 100) if total_entries > 0 else 0
        
        # Notification metrics
        notified = sum(1 for e in entries if e.status == WaitlistStatus.NOTIFIED)
        avg_notifications = (
            sum(e.notified_count for e in entries) / total_entries
            if total_entries > 0 else 0
        )
        
        # Time metrics
        avg_days_on_waitlist = (
            sum(e.days_on_waitlist for e in entries) / total_entries
            if total_entries > 0 else 0
        )
        
        active_entries = [e for e in entries if e.is_active]
        
        return {
            "total_entries": total_entries,
            "active_entries": len(active_entries),
            "entries_by_status": by_status,
            "entries_by_room_type": by_room_type,
            "converted_count": converted,
            "conversion_rate": conversion_rate,
            "notified_count": notified,
            "average_notifications_per_entry": avg_notifications,
            "average_days_on_waitlist": avg_days_on_waitlist,
        }


class WaitlistNotificationRepository(BaseRepository[WaitlistNotification]):
    """Repository for waitlist notification management."""
    
    def __init__(self, session: Session):
        """Initialize notification repository."""
        super().__init__(session, WaitlistNotification)
    
    def find_by_waitlist(
        self,
        waitlist_id: UUID,
    ) -> List[WaitlistNotification]:
        """
        Find notifications for a waitlist entry.
        
        Args:
            waitlist_id: Waitlist UUID
            
        Returns:
            List of notifications
        """
        query = select(WaitlistNotification).where(
            WaitlistNotification.waitlist_id == waitlist_id
        ).order_by(
            WaitlistNotification.sent_at.desc()
        ).options(
            joinedload(WaitlistNotification.available_room),
            joinedload(WaitlistNotification.available_bed),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def record_response(
        self,
        notification_id: UUID,
        response: str,
        audit_context: Optional[AuditContext] = None,
    ) -> WaitlistNotification:
        """
        Record visitor response to notification.
        
        Args:
            notification_id: Notification UUID
            response: Visitor response (accepted/declined)
            audit_context: Audit context
            
        Returns:
            Updated notification
        """
        notification = self.find_by_id(notification_id)
        if not notification:
            raise EntityNotFoundError(f"Notification {notification_id} not found")
        
        notification.record_response(response)
        
        self.session.flush()
        self.session.refresh(notification)
        
        return notification
    
    def find_pending_responses(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[WaitlistNotification]:
        """
        Find notifications awaiting response.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of notifications pending response
        """
        query = select(WaitlistNotification).join(
            BookingWaitlist,
            WaitlistNotification.waitlist_id == BookingWaitlist.id
        ).where(
            and_(
                WaitlistNotification.visitor_response.is_(None),
                WaitlistNotification.response_deadline > datetime.utcnow(),
            )
        )
        
        if hostel_id:
            query = query.where(BookingWaitlist.hostel_id == hostel_id)
        
        query = query.order_by(
            WaitlistNotification.response_deadline.asc()
        ).options(
            joinedload(WaitlistNotification.waitlist),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_expiring_soon(
        self,
        within_hours: int = 6,
        hostel_id: Optional[UUID] = None,
    ) -> List[WaitlistNotification]:
        """
        Find notifications with deadline expiring soon.
        
        Args:
            within_hours: Hours threshold
            hostel_id: Optional hostel filter
            
        Returns:
            List of notifications expiring soon
        """
        query = select(WaitlistNotification).join(
            BookingWaitlist,
            WaitlistNotification.waitlist_id == BookingWaitlist.id
        ).where(
            WaitlistNotification.visitor_response.is_(None)
        )
        
        if hostel_id:
            query = query.where(BookingWaitlist.hostel_id == hostel_id)
        
        notifications = self.session.execute(query).scalars().all()
        
        # Filter for expiring soon
        expiring = [n for n in notifications if n.is_expiring_soon]
        
        return expiring


