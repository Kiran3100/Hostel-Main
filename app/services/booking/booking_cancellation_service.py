# app/services/booking/booking_cancellation_service.py
"""
Booking cancellation service for cancellation and refund management.

Handles cancellation processing, refund calculations, policy application,
and refund transaction tracking.
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
from app.models.base.enums import BookingStatus, PaymentStatus
from app.repositories.booking.booking_repository import BookingRepository
from app.repositories.booking.booking_cancellation_repository import (
    BookingCancellationRepository,
    CancellationPolicyRepository,
    RefundTransactionRepository,
)
from app.repositories.base.base_repository import AuditContext


class BookingCancellationService:
    """
    Service for booking cancellation and refund management.
    
    Responsibilities:
    - Process cancellation requests
    - Calculate refunds based on policy
    - Manage refund transactions
    - Track cancellation metrics
    - Configure cancellation policies
    """
    
    def __init__(
        self,
        session: Session,
        booking_repo: Optional[BookingRepository] = None,
        cancellation_repo: Optional[BookingCancellationRepository] = None,
        policy_repo: Optional[CancellationPolicyRepository] = None,
        refund_repo: Optional[RefundTransactionRepository] = None,
    ):
        """Initialize cancellation service."""
        self.session = session
        self.booking_repo = booking_repo or BookingRepository(session)
        self.cancellation_repo = (
            cancellation_repo or BookingCancellationRepository(session)
        )
        self.policy_repo = policy_repo or CancellationPolicyRepository(session)
        self.refund_repo = refund_repo or RefundTransactionRepository(session)
    
    # ==================== CANCELLATION OPERATIONS ====================
    
    def cancel_booking(
        self,
        booking_id: UUID,
        cancelled_by_id: UUID,
        reason: str,
        request_refund: bool = True,
        canceller_role: str = "visitor",
        additional_comments: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Cancel a booking with refund calculation.
        
        Args:
            booking_id: Booking UUID
            cancelled_by_id: User UUID cancelling
            reason: Cancellation reason
            request_refund: Whether to request refund
            canceller_role: Role of canceller
            additional_comments: Additional context
            audit_context: Audit context
            
        Returns:
            Cancellation record with refund details
            
        Raises:
            EntityNotFoundError: If booking not found
            BusinessRuleViolationError: If cancellation not allowed
        """
        # Get booking
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        # Validate booking can be cancelled
        if booking.booking_status in [
            BookingStatus.CANCELLED,
            BookingStatus.COMPLETED,
        ]:
            raise BusinessRuleViolationError(
                f"Cannot cancel booking with status {booking.booking_status}"
            )
        
        # Calculate refund
        refund_details = self._calculate_refund(booking)
        
        # Create cancellation record
        cancellation_data = {
            "cancelled_by_role": canceller_role,
            "cancellation_reason": reason,
            "additional_comments": additional_comments,
            "request_refund": request_refund,
            "advance_paid": refund_details["advance_paid"],
            "cancellation_charge": refund_details["cancellation_charge"],
            "cancellation_charge_percentage": refund_details["charge_percentage"],
            "refundable_amount": refund_details["refundable_amount"],
            "refund_processing_time_days": refund_details["processing_days"],
            "refund_breakdown": refund_details["breakdown"],
        }
        
        cancellation = self.cancellation_repo.create_cancellation(
            booking_id, cancellation_data, audit_context
        )
        
        # Update booking status
        self.booking_repo.cancel_booking(
            booking_id, cancelled_by_id, reason, audit_context
        )
        
        # Initiate refund if requested and amount > 0
        if request_refund and refund_details["refundable_amount"] > 0:
            self._initiate_refund_processing(cancellation.id, audit_context)
        
        return self._cancellation_to_dict(cancellation)
    
    def _calculate_refund(self, booking) -> Dict:
        """
        Calculate refund amount based on cancellation policy.
        
        Args:
            booking: Booking model instance
            
        Returns:
            Refund calculation details
        """
        advance_paid = booking.advance_amount if booking.advance_paid else Decimal("0.00")
        
        if advance_paid == 0:
            return {
                "advance_paid": Decimal("0.00"),
                "cancellation_charge": Decimal("0.00"),
                "charge_percentage": Decimal("0.00"),
                "refundable_amount": Decimal("0.00"),
                "processing_days": 0,
                "breakdown": {},
            }
        
        # Get active cancellation policy
        policy = self.policy_repo.find_active_by_hostel(booking.hostel_id)
        
        if not policy:
            # No policy: full refund minus small processing fee
            processing_fee = Decimal("100.00")  # Fixed ₹100
            refundable = max(advance_paid - processing_fee, Decimal("0.00"))
            
            return {
                "advance_paid": advance_paid,
                "cancellation_charge": processing_fee,
                "charge_percentage": (processing_fee / advance_paid * 100).quantize(
                    Decimal("0.01")
                )
                if advance_paid > 0
                else Decimal("0.00"),
                "refundable_amount": refundable,
                "processing_days": 7,
                "breakdown": {
                    "advance_paid": float(advance_paid),
                    "processing_fee": float(processing_fee),
                    "refundable": float(refundable),
                },
            }
        
        # Calculate based on policy
        days_before_checkin = (booking.preferred_check_in_date - date.today()).days
        
        charge, charge_pct, refundable = self.cancellation_repo.calculate_refund_amount(
            booking, policy
        )
        
        return {
            "advance_paid": advance_paid,
            "cancellation_charge": charge,
            "charge_percentage": charge_pct,
            "refundable_amount": refundable,
            "processing_days": policy.refund_processing_days,
            "breakdown": {
                "advance_paid": float(advance_paid),
                "days_before_checkin": days_before_checkin,
                "cancellation_charge": float(charge),
                "charge_percentage": float(charge_pct),
                "refundable_amount": float(refundable),
                "policy_name": policy.policy_name,
            },
        }
    
    def _initiate_refund_processing(
        self,
        cancellation_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> None:
        """Initiate refund processing workflow."""
        self.cancellation_repo.initiate_refund(cancellation_id, audit_context)
    
    # ==================== REFUND MANAGEMENT ====================
    
    def process_refund(
        self,
        cancellation_id: UUID,
        refund_method: str = "bank_transfer",
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Process refund for a cancellation.
        
        Args:
            cancellation_id: Cancellation UUID
            refund_method: Refund method
            audit_context: Audit context
            
        Returns:
            Updated cancellation with refund status
        """
        cancellation = self.cancellation_repo.find_by_id(cancellation_id)
        if not cancellation:
            raise EntityNotFoundError(f"Cancellation {cancellation_id} not found")
        
        # Create refund transaction
        refund_data = {
            "cancellation_id": cancellation_id,
            "booking_id": cancellation.booking_id,
            "refund_amount": cancellation.refundable_amount,
            "refund_method": refund_method,
            "refund_status": PaymentStatus.PROCESSING,
        }
        
        refund_transaction = self.refund_repo.create_refund_transaction(
            refund_data, audit_context
        )
        
        # Update cancellation
        self.cancellation_repo.initiate_refund(cancellation_id, audit_context)
        
        return self._cancellation_to_dict(cancellation)
    
    def complete_refund(
        self,
        cancellation_id: UUID,
        transaction_id: UUID,
        gateway_transaction_id: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Mark refund as completed.
        
        Args:
            cancellation_id: Cancellation UUID
            transaction_id: Refund transaction UUID
            gateway_transaction_id: External gateway ID
            audit_context: Audit context
            
        Returns:
            Updated cancellation
        """
        cancellation = self.cancellation_repo.complete_refund(
            cancellation_id, transaction_id, audit_context
        )
        
        return self._cancellation_to_dict(cancellation)
    
    def fail_refund(
        self,
        cancellation_id: UUID,
        reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Mark refund as failed.
        
        Args:
            cancellation_id: Cancellation UUID
            reason: Failure reason
            audit_context: Audit context
            
        Returns:
            Updated cancellation
        """
        cancellation = self.cancellation_repo.fail_refund(
            cancellation_id, reason, audit_context
        )
        
        return self._cancellation_to_dict(cancellation)
    
    # ==================== REFUND QUERIES ====================
    
    def get_pending_refunds(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Get cancellations with pending refunds."""
        cancellations = self.cancellation_repo.find_pending_refunds(hostel_id)
        return [self._cancellation_to_dict(c) for c in cancellations]
    
    def get_processing_refunds(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Get refunds currently being processed."""
        cancellations = self.cancellation_repo.find_processing_refunds(hostel_id)
        return [self._cancellation_to_dict(c) for c in cancellations]
    
    def get_overdue_refunds(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Get refunds that are overdue."""
        cancellations = self.cancellation_repo.find_overdue_refunds(hostel_id)
        return [self._cancellation_to_dict(c) for c in cancellations]
    
    # ==================== CANCELLATION POLICY ====================
    
    def configure_cancellation_policy(
        self,
        hostel_id: UUID,
        policy_name: str,
        cancellation_tiers: List[Dict],
        no_show_charge_percentage: Decimal = Decimal("100.00"),
        refund_processing_days: int = 7,
        policy_text: str = "",
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Configure cancellation policy for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            policy_name: Policy name
            cancellation_tiers: Tier structure
            no_show_charge_percentage: No-show charge
            refund_processing_days: Processing time
            policy_text: Policy text
            audit_context: Audit context
            
        Returns:
            Created/updated policy dictionary
            
        Example cancellation_tiers:
        [
            {"days_before_checkin": 30, "charge_percentage": 10},
            {"days_before_checkin": 15, "charge_percentage": 25},
            {"days_before_checkin": 7, "charge_percentage": 50},
            {"days_before_checkin": 0, "charge_percentage": 100},
        ]
        """
        policy_data = {
            "policy_name": policy_name,
            "cancellation_tiers": cancellation_tiers,
            "no_show_charge_percentage": no_show_charge_percentage,
            "refund_processing_days": refund_processing_days,
            "policy_text": policy_text,
        }
        
        policy = self.policy_repo.create_or_update_policy(
            hostel_id, policy_data, audit_context
        )
        
        return self._policy_to_dict(policy)
    
    def get_cancellation_policy(
        self,
        hostel_id: UUID,
    ) -> Optional[Dict]:
        """Get active cancellation policy for a hostel."""
        policy = self.policy_repo.find_active_by_hostel(hostel_id)
        return self._policy_to_dict(policy) if policy else None
    
    def get_all_policies(
        self,
        hostel_id: UUID,
        include_inactive: bool = False,
    ) -> List[Dict]:
        """Get all cancellation policies for a hostel."""
        policies = self.policy_repo.find_by_hostel(hostel_id, include_inactive)
        return [self._policy_to_dict(p) for p in policies]
    
    # ==================== ANALYTICS ====================
    
    def get_cancellation_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict:
        """Get cancellation statistics."""
        return self.cancellation_repo.get_cancellation_statistics(
            hostel_id, date_from, date_to
        )
    
    # ==================== HELPER METHODS ====================
    
    def _cancellation_to_dict(self, cancellation) -> Dict:
        """Convert cancellation model to dictionary."""
        return {
            "id": str(cancellation.id),
            "booking_id": str(cancellation.booking_id),
            "cancelled_by": (
                str(cancellation.cancelled_by) if cancellation.cancelled_by else None
            ),
            "cancelled_by_role": cancellation.cancelled_by_role,
            "cancelled_at": cancellation.cancelled_at.isoformat(),
            "cancellation_reason": cancellation.cancellation_reason,
            "additional_comments": cancellation.additional_comments,
            "request_refund": cancellation.request_refund,
            "advance_paid": float(cancellation.advance_paid),
            "cancellation_charge": float(cancellation.cancellation_charge),
            "cancellation_charge_percentage": float(
                cancellation.cancellation_charge_percentage
            ),
            "refundable_amount": float(cancellation.refundable_amount),
            "refund_processing_time_days": cancellation.refund_processing_time_days,
            "refund_method": cancellation.refund_method,
            "refund_status": cancellation.refund_status.value,
            "refund_breakdown": cancellation.refund_breakdown,
            "is_refund_pending": cancellation.is_refund_pending,
            "is_refund_completed": cancellation.is_refund_completed,
            "days_since_cancellation": cancellation.days_since_cancellation,
            "expected_refund_date": (
                cancellation.expected_refund_date.isoformat()
                if cancellation.expected_refund_date
                else None
            ),
        }
    
    def _policy_to_dict(self, policy) -> Dict:
        """Convert policy model to dictionary."""
        return {
            "id": str(policy.id),
            "hostel_id": str(policy.hostel_id),
            "policy_name": policy.policy_name,
            "cancellation_tiers": policy.cancellation_tiers,
            "no_show_charge_percentage": float(policy.no_show_charge_percentage),
            "refund_processing_days": policy.refund_processing_days,
            "policy_text": policy.policy_text,
            "is_active": policy.is_active,
            "effective_from": policy.effective_from.isoformat(),
            "effective_until": (
                policy.effective_until.isoformat() if policy.effective_until else None
            ),
        }