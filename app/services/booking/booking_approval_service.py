# app/services/booking/booking_approval_service.py
"""
Booking approval service for comprehensive approval workflow management.

Handles approval decisions, auto-approval logic, rejection processing,
and approval policy management.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ValidationError,
)
from app.models.base.enums import BookingStatus, RoomType
from app.repositories.booking.booking_repository import BookingRepository
from app.repositories.booking.booking_approval_repository import (
    ApprovalSettingsRepository,
    BookingApprovalRepository,
    RejectionRecordRepository,
)
from app.repositories.base.base_repository import AuditContext


class BookingApprovalService:
    """
    Service for booking approval workflow management.
    
    Responsibilities:
    - Process approval decisions
    - Handle auto-approval logic
    - Manage rejection with alternatives
    - Configure approval policies
    - Calculate payment requirements
    - Track approval metrics
    """
    
    def __init__(
        self,
        session: Session,
        booking_repo: Optional[BookingRepository] = None,
        approval_repo: Optional[BookingApprovalRepository] = None,
        settings_repo: Optional[ApprovalSettingsRepository] = None,
        rejection_repo: Optional[RejectionRecordRepository] = None,
    ):
        """Initialize approval service."""
        self.session = session
        self.booking_repo = booking_repo or BookingRepository(session)
        self.approval_repo = approval_repo or BookingApprovalRepository(session)
        self.settings_repo = settings_repo or ApprovalSettingsRepository(session)
        self.rejection_repo = rejection_repo or RejectionRecordRepository(session)
    
    # ==================== APPROVAL OPERATIONS ====================
    
    def approve_booking(
        self,
        booking_id: UUID,
        approved_by_id: UUID,
        final_pricing: Optional[Dict] = None,
        approval_notes: Optional[str] = None,
        message_to_guest: Optional[str] = None,
        advance_payment_percentage: Optional[Decimal] = None,
        payment_deadline_hours: int = 72,
        auto_approved: bool = False,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Approve a pending booking with complete approval workflow.
        
        Args:
            booking_id: Booking UUID
            approved_by_id: Admin UUID approving
            final_pricing: Optional pricing adjustments
            approval_notes: Internal notes
            message_to_guest: Message to send to guest
            advance_payment_percentage: Advance payment percentage
            payment_deadline_hours: Hours to make payment
            auto_approved: Whether this is auto-approval
            audit_context: Audit context
            
        Returns:
            Approval record dictionary
            
        Raises:
            EntityNotFoundError: If booking not found
            BusinessRuleViolationError: If booking cannot be approved
        """
        # Get booking
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        # Validate status
        if booking.booking_status != BookingStatus.PENDING:
            raise BusinessRuleViolationError(
                f"Cannot approve booking with status {booking.booking_status}"
            )
        
        # Check for existing approval
        existing_approval = self.approval_repo.find_by_booking(booking_id)
        if existing_approval:
            raise BusinessRuleViolationError("Booking is already approved")
        
        # Prepare approval data
        approval_data = self._prepare_approval_data(
            booking,
            final_pricing,
            advance_payment_percentage,
            payment_deadline_hours,
            approval_notes,
            message_to_guest,
            auto_approved,
        )
        
        # Create approval record
        approval = self.approval_repo.create_approval_record(
            booking_id, approval_data, audit_context
        )
        
        # Update booking status
        self.booking_repo.approve_booking(booking_id, approved_by_id, audit_context)
        
        # Set payment deadline if required
        if approval.advance_payment_required:
            self.approval_repo.set_payment_deadline(
                booking_id, payment_deadline_hours
            )
        
        return self._approval_to_dict(approval)
    
    def _prepare_approval_data(
        self,
        booking,
        final_pricing: Optional[Dict],
        advance_payment_percentage: Optional[Decimal],
        payment_deadline_hours: int,
        approval_notes: Optional[str],
        message_to_guest: Optional[str],
        auto_approved: bool,
    ) -> Dict:
        """Prepare approval data with pricing calculations."""
        # Use final pricing if provided, otherwise use booking pricing
        final_rent = (
            Decimal(str(final_pricing["monthly_rent"]))
            if final_pricing
            else booking.quoted_rent_monthly
        )
        
        security_deposit = (
            Decimal(str(final_pricing.get("security_deposit", 0)))
            if final_pricing
            else booking.security_deposit
        )
        
        processing_fee = (
            Decimal(str(final_pricing.get("processing_fee", 0)))
            if final_pricing
            else Decimal("0.00")
        )
        
        # Calculate total amount
        total_amount = (final_rent * booking.stay_duration_months) + processing_fee
        
        # Calculate advance payment
        advance_percentage = advance_payment_percentage or Decimal("20.00")
        advance_amount = (total_amount * advance_percentage / 100).quantize(
            Decimal("0.01")
        )
        
        return {
            "final_rent_monthly": final_rent,
            "final_security_deposit": security_deposit,
            "processing_fee": processing_fee,
            "total_amount": total_amount,
            "advance_payment_required": True,
            "advance_payment_percentage": advance_percentage,
            "advance_payment_amount": advance_amount,
            "advance_payment_deadline": datetime.utcnow()
            + timedelta(hours=payment_deadline_hours),
            "admin_notes": approval_notes,
            "message_to_guest": message_to_guest,
            "auto_approved": auto_approved,
        }
    
    def reject_booking(
        self,
        booking_id: UUID,
        rejected_by_id: UUID,
        reason: str,
        suggest_alternatives: bool = False,
        alternative_dates: Optional[List] = None,
        alternative_room_types: Optional[List[RoomType]] = None,
        message_to_guest: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Reject a pending booking with optional alternatives.
        
        Args:
            booking_id: Booking UUID
            rejected_by_id: Admin UUID rejecting
            reason: Rejection reason
            suggest_alternatives: Whether to suggest alternatives
            alternative_dates: Alternative check-in dates
            alternative_room_types: Alternative room types
            message_to_guest: Message to guest
            audit_context: Audit context
            
        Returns:
            Rejection record dictionary
        """
        # Get booking
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        # Validate status
        if booking.booking_status != BookingStatus.PENDING:
            raise BusinessRuleViolationError(
                f"Cannot reject booking with status {booking.booking_status}"
            )
        
        # Create rejection record
        rejection_data = {
            "rejection_reason": reason,
            "suggest_alternative_dates": suggest_alternatives and bool(alternative_dates),
            "alternative_check_in_dates": (
                [d.isoformat() for d in alternative_dates] if alternative_dates else None
            ),
            "suggest_alternative_room_types": suggest_alternatives
            and bool(alternative_room_types),
            "alternative_room_types": (
                [rt.value for rt in alternative_room_types]
                if alternative_room_types
                else None
            ),
            "message_to_guest": message_to_guest,
        }
        
        rejection = self.rejection_repo.create_rejection_record(
            booking_id, rejection_data, audit_context
        )
        
        # Update booking status
        self.booking_repo.reject_booking(
            booking_id, rejected_by_id, reason, audit_context
        )
        
        return self._rejection_to_dict(rejection)
    
    # ==================== AUTO-APPROVAL ====================
    
    def check_auto_approval_eligibility(
        self,
        booking_id: UUID,
    ) -> Dict:
        """
        Check if booking is eligible for auto-approval.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Eligibility details dictionary
        """
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        # Get approval settings
        settings = self.settings_repo.find_by_hostel(booking.hostel_id)
        
        if not settings or not settings.auto_approve_enabled:
            return {
                "eligible": False,
                "reason": "Auto-approval not enabled for this hostel",
            }
        
        # Check criteria
        booking_data = {
            "total_amount": booking.total_amount,
            "stay_duration_months": booking.stay_duration_months,
            "room_type_requested": booking.room_type_requested,
        }
        
        should_auto_approve, criteria_met = (
            self.settings_repo.check_auto_approval_criteria(
                booking.hostel_id, booking_data
            )
        )
        
        return {
            "eligible": should_auto_approve,
            "criteria_met": criteria_met,
            "settings": self._approval_settings_to_dict(settings),
        }
    
    # ==================== APPROVAL SETTINGS ====================
    
    def configure_approval_settings(
        self,
        hostel_id: UUID,
        auto_approve_enabled: bool = False,
        auto_approve_conditions: Optional[Dict] = None,
        approval_expiry_hours: int = 48,
        require_advance_payment: bool = True,
        advance_payment_percentage: Decimal = Decimal("20.00"),
        advance_payment_deadline_hours: int = 72,
        refund_processing_days: int = 7,
        policy_text: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Configure approval settings for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            auto_approve_enabled: Enable auto-approval
            auto_approve_conditions: Auto-approval criteria
            approval_expiry_hours: Hours for approval expiry
            require_advance_payment: Require advance payment
            advance_payment_percentage: Advance percentage
            advance_payment_deadline_hours: Payment deadline
            refund_processing_days: Refund processing time
            policy_text: Policy text
            audit_context: Audit context
            
        Returns:
            Approval settings dictionary
        """
        settings_data = {
            "auto_approve_enabled": auto_approve_enabled,
            "auto_approve_conditions": auto_approve_conditions,
            "approval_expiry_hours": approval_expiry_hours,
            "require_advance_payment": require_advance_payment,
            "advance_payment_percentage": advance_payment_percentage,
            "advance_payment_deadline_hours": advance_payment_deadline_hours,
            "refund_processing_days": refund_processing_days,
            "approval_policy_text": policy_text,
        }
        
        settings = self.settings_repo.create_or_update_settings(
            hostel_id, settings_data, audit_context
        )
        
        return self._approval_settings_to_dict(settings)
    
    def get_approval_settings(self, hostel_id: UUID) -> Optional[Dict]:
        """Get approval settings for a hostel."""
        settings = self.settings_repo.find_by_hostel(hostel_id)
        return self._approval_settings_to_dict(settings) if settings else None
    
    # ==================== PAYMENT TRACKING ====================
    
    def get_pending_payments(
        self,
        hostel_id: Optional[UUID] = None,
        overdue_only: bool = False,
    ) -> List[Dict]:
        """
        Get approvals with pending advance payments.
        
        Args:
            hostel_id: Optional hostel filter
            overdue_only: Only overdue payments
            
        Returns:
            List of approval dictionaries
        """
        approvals = self.approval_repo.find_pending_payment(hostel_id, overdue_only)
        return [self._approval_to_dict(a) for a in approvals]
    
    def get_payment_expiring_soon(
        self,
        within_hours: int = 24,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Get approvals with payment deadline expiring soon."""
        approvals = self.approval_repo.find_payment_expiring_soon(
            within_hours, hostel_id
        )
        return [self._approval_to_dict(a) for a in approvals]
    
    # ==================== ANALYTICS ====================
    
    def get_approval_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict:
        """Get approval statistics."""
        return self.approval_repo.get_approval_statistics(hostel_id, date_from, date_to)
    
    def get_rejection_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict:
        """Get rejection statistics."""
        return self.rejection_repo.get_rejection_statistics(
            hostel_id, date_from, date_to
        )
    
    def get_auto_approved_bookings(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict]:
        """Get auto-approved bookings."""
        approvals = self.approval_repo.find_auto_approved(hostel_id, date_from, date_to)
        return [self._approval_to_dict(a) for a in approvals]
    
    # ==================== HELPER METHODS ====================
    
    def _approval_to_dict(self, approval) -> Dict:
        """Convert approval model to dictionary."""
        return {
            "id": str(approval.id),
            "booking_id": str(approval.booking_id),
            "approved_by": str(approval.approved_by) if approval.approved_by else None,
            "approved_at": approval.approved_at.isoformat(),
            "final_rent_monthly": float(approval.final_rent_monthly),
            "final_security_deposit": float(approval.final_security_deposit),
            "processing_fee": float(approval.processing_fee),
            "total_amount": float(approval.total_amount),
            "advance_payment_required": approval.advance_payment_required,
            "advance_payment_percentage": float(approval.advance_payment_percentage),
            "advance_payment_amount": float(approval.advance_payment_amount),
            "advance_payment_deadline": (
                approval.advance_payment_deadline.isoformat()
                if approval.advance_payment_deadline
                else None
            ),
            "auto_approved": approval.auto_approved,
            "admin_notes": approval.admin_notes,
            "message_to_guest": approval.message_to_guest,
            "is_payment_overdue": approval.is_payment_overdue,
            "days_until_payment_deadline": approval.days_until_payment_deadline,
        }
    
    def _rejection_to_dict(self, rejection) -> Dict:
        """Convert rejection model to dictionary."""
        return {
            "id": str(rejection.id),
            "booking_id": str(rejection.booking_id),
            "rejected_by": str(rejection.rejected_by) if rejection.rejected_by else None,
            "rejected_at": rejection.rejected_at.isoformat(),
            "rejection_reason": rejection.rejection_reason,
            "suggest_alternative_dates": rejection.suggest_alternative_dates,
            "alternative_check_in_dates": rejection.alternative_check_in_dates,
            "suggest_alternative_room_types": rejection.suggest_alternative_room_types,
            "alternative_room_types": rejection.alternative_room_types,
            "message_to_guest": rejection.message_to_guest,
        }
    
    def _approval_settings_to_dict(self, settings) -> Dict:
        """Convert approval settings to dictionary."""
        return {
            "id": str(settings.id),
            "hostel_id": str(settings.hostel_id),
            "auto_approve_enabled": settings.auto_approve_enabled,
            "auto_approve_conditions": settings.auto_approve_conditions,
            "approval_expiry_hours": settings.approval_expiry_hours,
            "require_advance_payment": settings.require_advance_payment,
            "advance_payment_percentage": float(settings.advance_payment_percentage),
            "advance_payment_deadline_hours": settings.advance_payment_deadline_hours,
            "refund_processing_days": settings.refund_processing_days,
            "approval_policy_text": settings.approval_policy_text,
            "has_auto_approval": settings.has_auto_approval,
        }