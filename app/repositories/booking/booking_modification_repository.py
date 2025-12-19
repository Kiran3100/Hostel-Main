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
