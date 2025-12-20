# app/services/booking/booking_modification_service.py
"""
Booking modification service for modification request management.

Handles modification requests, pricing impact analysis, approval workflows,
and modification application.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ValidationError,
)
from app.models.base.enums import RoomType
from app.repositories.booking.booking_repository import BookingRepository
from app.repositories.booking.booking_modification_repository import (
    BookingModificationRepository,
    ModificationApprovalRecordRepository,
)
from app.repositories.base.base_repository import AuditContext


class BookingModificationService:
    """
    Service for booking modification request management.
    
    Responsibilities:
    - Process modification requests
    - Calculate pricing impact
    - Manage approval workflow
    - Apply approved modifications
    - Track modification analytics
    """
    
    def __init__(
        self,
        session: Session,
        booking_repo: Optional[BookingRepository] = None,
        modification_repo: Optional[BookingModificationRepository] = None,
        approval_record_repo: Optional[ModificationApprovalRecordRepository] = None,
    ):
        """Initialize modification service."""
        self.session = session
        self.booking_repo = booking_repo or BookingRepository(session)
        self.modification_repo = (
            modification_repo or BookingModificationRepository(session)
        )
        self.approval_record_repo = (
            approval_record_repo or ModificationApprovalRecordRepository(session)
        )
    
    # ==================== MODIFICATION REQUEST ====================
    
    def request_modification(
        self,
        booking_id: UUID,
        requested_by_id: UUID,
        modification_reason: str,
        modify_check_in_date: bool = False,
        new_check_in_date: Optional[date] = None,
        modify_duration: bool = False,
        new_duration_months: Optional[int] = None,
        modify_room_type: bool = False,
        new_room_type: Optional[RoomType] = None,
        accept_price_change: bool = False,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Create modification request for a booking.
        
        Args:
            booking_id: Booking UUID
            requested_by_id: User UUID requesting
            modification_reason: Reason for modification
            modify_check_in_date: Whether to modify check-in
            new_check_in_date: New check-in date
            modify_duration: Whether to modify duration
            new_duration_months: New duration
            modify_room_type: Whether to modify room type
            new_room_type: New room type
            accept_price_change: Whether user accepts price changes
            audit_context: Audit context
            
        Returns:
            Created modification dictionary
            
        Raises:
            EntityNotFoundError: If booking not found
            ValidationError: If validation fails
        """
        # Validate at least one modification type is specified
        if not any([modify_check_in_date, modify_duration, modify_room_type]):
            raise ValidationError(
                "At least one modification type must be specified"
            )
        
        # Build modification data
        modification_data = {
            "modification_reason": modification_reason,
            "modify_check_in_date": modify_check_in_date,
            "new_check_in_date": new_check_in_date,
            "modify_duration": modify_duration,
            "new_duration_months": new_duration_months,
            "modify_room_type": modify_room_type,
            "new_room_type": new_room_type,
            "accept_price_change": accept_price_change,
        }
        
        modification = self.modification_repo.create_modification_request(
            booking_id, modification_data, audit_context
        )
        
        return self._modification_to_dict(modification)
    
    def calculate_modification_price_impact(
        self,
        modification_id: UUID,
        new_monthly_rent: Decimal,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Calculate pricing impact of modification.
        
        Args:
            modification_id: Modification UUID
            new_monthly_rent: New monthly rent
            audit_context: Audit context
            
        Returns:
            Updated modification with price impact
        """
        modification = self.modification_repo.calculate_price_impact(
            modification_id, new_monthly_rent, audit_context
        )
        
        return self._modification_to_dict(modification)
    
    # ==================== APPROVAL WORKFLOW ====================
    
    def approve_modification(
        self,
        modification_id: UUID,
        approved_by_id: UUID,
        approval_notes: Optional[str] = None,
        adjusted_price: Optional[Decimal] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Approve modification request.
        
        Args:
            modification_id: Modification UUID
            approved_by_id: Admin UUID
            approval_notes: Approval notes
            adjusted_price: Admin-adjusted price
            audit_context: Audit context
            
        Returns:
            Approved modification dictionary
        """
        modification = self.modification_repo.approve_modification(
            modification_id,
            approved_by_id,
            approval_notes,
            adjusted_price,
            audit_context,
        )
        
        return self._modification_to_dict(modification)
    
    def reject_modification(
        self,
        modification_id: UUID,
        rejected_by_id: UUID,
        rejection_reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Reject modification request.
        
        Args:
            modification_id: Modification UUID
            rejected_by_id: Admin UUID
            rejection_reason: Rejection reason
            audit_context: Audit context
            
        Returns:
            Rejected modification dictionary
        """
        modification = self.modification_repo.reject_modification(
            modification_id, rejected_by_id, rejection_reason, audit_context
        )
        
        return self._modification_to_dict(modification)
    
    def apply_modification(
        self,
        modification_id: UUID,
        applied_by_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Apply approved modification to booking.
        
        Args:
            modification_id: Modification UUID
            applied_by_id: Admin UUID
            audit_context: Audit context
            
        Returns:
            Dictionary with modification and updated booking
            
        Raises:
            BusinessRuleViolationError: If modification cannot be applied
        """
        modification, booking = self.modification_repo.apply_modification(
            modification_id, applied_by_id, audit_context
        )
        
        return {
            "modification": self._modification_to_dict(modification),
            "booking": self._booking_to_dict(booking),
        }
    
    # ==================== MODIFICATION QUERIES ====================
    
    def get_booking_modifications(
        self,
        booking_id: UUID,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get all modification requests for a booking.
        
        Args:
            booking_id: Booking UUID
            status: Optional status filter
            
        Returns:
            List of modification dictionaries
        """
        modifications = self.modification_repo.find_by_booking(booking_id, status)
        return [self._modification_to_dict(m) for m in modifications]
    
    def get_pending_modifications(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """
        Get pending modification requests.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of pending modification dictionaries
        """
        modifications = self.modification_repo.find_pending_modifications(hostel_id)
        return [self._modification_to_dict(m) for m in modifications]
    
    def get_modifications_by_type(
        self,
        modification_type: str,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict]:
        """Get modifications by type."""
        modifications = self.modification_repo.find_by_type(
            modification_type, hostel_id, date_from, date_to
        )
        return [self._modification_to_dict(m) for m in modifications]
    
    def get_modifications_with_price_increase(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Get modifications resulting in price increase."""
        modifications = self.modification_repo.find_with_price_increase(hostel_id)
        return [self._modification_to_dict(m) for m in modifications]
    
    # ==================== ANALYTICS ====================
    
    def get_modification_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict:
        """
        Get modification statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics dictionary
        """
        return self.modification_repo.get_modification_statistics(
            hostel_id, date_from, date_to
        )
    
    # ==================== HELPER METHODS ====================
    
    def _modification_to_dict(self, modification) -> Dict:
        """Convert modification model to dictionary."""
        return {
            "id": str(modification.id),
            "booking_id": str(modification.booking_id),
            "modification_type": modification.modification_type,
            "requested_by": (
                str(modification.requested_by) if modification.requested_by else None
            ),
            "requested_at": modification.requested_at.isoformat(),
            "modification_reason": modification.modification_reason,
            # Check-in date modification
            "modify_check_in_date": modification.modify_check_in_date,
            "original_check_in_date": (
                modification.original_check_in_date.isoformat()
                if modification.original_check_in_date
                else None
            ),
            "new_check_in_date": (
                modification.new_check_in_date.isoformat()
                if modification.new_check_in_date
                else None
            ),
            # Duration modification
            "modify_duration": modification.modify_duration,
            "original_duration_months": modification.original_duration_months,
            "new_duration_months": modification.new_duration_months,
            # Room type modification
            "modify_room_type": modification.modify_room_type,
            "original_room_type": (
                modification.original_room_type.value
                if modification.original_room_type
                else None
            ),
            "new_room_type": (
                modification.new_room_type.value if modification.new_room_type else None
            ),
            # Price impact
            "accept_price_change": modification.accept_price_change,
            "original_total_amount": float(modification.original_total_amount),
            "new_total_amount": (
                float(modification.new_total_amount)
                if modification.new_total_amount
                else None
            ),
            "price_difference": (
                float(modification.price_difference)
                if modification.price_difference
                else None
            ),
            "additional_payment_required": modification.additional_payment_required,
            "additional_payment_amount": (
                float(modification.additional_payment_amount)
                if modification.additional_payment_amount
                else None
            ),
            # Status
            "modification_status": modification.modification_status,
            "approved_at": (
                modification.approved_at.isoformat() if modification.approved_at else None
            ),
            "approved_by": (
                str(modification.approved_by) if modification.approved_by else None
            ),
            "rejected_at": (
                modification.rejected_at.isoformat() if modification.rejected_at else None
            ),
            "rejected_by": (
                str(modification.rejected_by) if modification.rejected_by else None
            ),
            "rejection_reason": modification.rejection_reason,
            "applied_at": (
                modification.applied_at.isoformat() if modification.applied_at else None
            ),
            "applied_by": (
                str(modification.applied_by) if modification.applied_by else None
            ),
            # Computed properties
            "is_pending": modification.is_pending,
            "is_approved": modification.is_approved,
            "is_applied": modification.is_applied,
            "has_price_increase": modification.has_price_increase,
            "has_price_decrease": modification.has_price_decrease,
        }
    
    def _booking_to_dict(self, booking) -> Dict:
        """Convert booking model to dictionary."""
        return {
            "id": str(booking.id),
            "booking_reference": booking.booking_reference,
            "preferred_check_in_date": booking.preferred_check_in_date.isoformat(),
            "stay_duration_months": booking.stay_duration_months,
            "room_type_requested": booking.room_type_requested.value,
            "total_amount": float(booking.total_amount),
            "booking_status": booking.booking_status.value,
        }