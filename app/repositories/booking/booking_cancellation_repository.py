# app/repositories/booking/booking_cancellation_repository.py
"""
Booking cancellation repository for cancellation and refund management.

Provides cancellation tracking, refund calculations, policy management,
and refund processing workflows.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core1.exceptions import EntityNotFoundError, ValidationError
from app.models.booking.booking_cancellation import (
    BookingCancellation,
    CancellationPolicy,
    RefundTransaction,
)
from app.models.booking.booking import Booking
from app.models.base.enums import PaymentStatus
from app.repositories.base.base_repository import (
    AuditContext,
    BaseRepository,
    QueryOptions,
)


class BookingCancellationRepository(BaseRepository[BookingCancellation]):
    """
    Repository for booking cancellation operations.
    
    Provides:
    - Cancellation record management
    - Refund calculation and tracking
    - Refund status management
    - Cancellation analytics
    """
    
    def __init__(self, session: Session):
        """Initialize cancellation repository."""
        super().__init__(session, BookingCancellation)
    
    # ==================== CANCELLATION OPERATIONS ====================
    
    def create_cancellation(
        self,
        booking_id: UUID,
        cancellation_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingCancellation:
        """
        Create cancellation record for a booking.
        
        Args:
            booking_id: Booking UUID
            cancellation_data: Cancellation information
            audit_context: Audit context
            
        Returns:
            Created cancellation record
        """
        cancellation = BookingCancellation(
            booking_id=booking_id,
            cancelled_by=audit_context.user_id if audit_context else None,
            cancelled_at=datetime.utcnow(),
            **cancellation_data,
        )
        
        return self.create(cancellation, audit_context)
    
    def find_by_booking(self, booking_id: UUID) -> Optional[BookingCancellation]:
        """
        Find cancellation record for a booking.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Cancellation record if found
        """
        query = select(BookingCancellation).where(
            BookingCancellation.booking_id == booking_id
        ).where(
            BookingCancellation.deleted_at.is_(None)
        ).options(
            joinedload(BookingCancellation.booking),
            joinedload(BookingCancellation.canceller),
            joinedload(BookingCancellation.refund_transaction),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def calculate_refund_amount(
        self,
        booking: Booking,
        cancellation_policy: Optional[CancellationPolicy] = None,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate refund amount based on policy.
        
        Args:
            booking: Booking instance
            cancellation_policy: Optional specific policy (otherwise use hostel's)
            
        Returns:
            Tuple of (cancellation_charge, cancellation_charge_percentage, refundable_amount)
        """
        advance_paid = booking.advance_amount if booking.advance_paid else Decimal("0.00")
        
        if not cancellation_policy:
            # Get default policy for hostel
            policy_repo = CancellationPolicyRepository(self.session)
            cancellation_policy = policy_repo.find_active_by_hostel(booking.hostel_id)
        
        if not cancellation_policy:
            # No policy: full refund
            return Decimal("0.00"), Decimal("0.00"), advance_paid
        
        # Calculate days before check-in
        days_before = (booking.preferred_check_in_date - date.today()).days
        
        # Calculate cancellation charge
        charge = cancellation_policy.calculate_cancellation_charge(
            days_before,
            advance_paid
        )
        
        # Calculate percentage
        charge_percentage = (charge / advance_paid * 100).quantize(Decimal("0.01")) if advance_paid > 0 else Decimal("0.00")
        
        # Calculate refundable amount
        refundable = (advance_paid - charge).quantize(Decimal("0.01"))
        
        return charge, charge_percentage, refundable
    
    def initiate_refund(
        self,
        cancellation_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingCancellation:
        """
        Initiate refund processing.
        
        Args:
            cancellation_id: Cancellation UUID
            audit_context: Audit context
            
        Returns:
            Updated cancellation
        """
        cancellation = self.find_by_id(cancellation_id)
        if not cancellation:
            raise EntityNotFoundError(f"Cancellation {cancellation_id} not found")
        
        cancellation.initiate_refund()
        
        self.session.flush()
        self.session.refresh(cancellation)
        
        return cancellation
    
    def complete_refund(
        self,
        cancellation_id: UUID,
        transaction_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingCancellation:
        """
        Mark refund as completed.
        
        Args:
            cancellation_id: Cancellation UUID
            transaction_id: Refund transaction UUID
            audit_context: Audit context
            
        Returns:
            Updated cancellation
        """
        cancellation = self.find_by_id(cancellation_id)
        if not cancellation:
            raise EntityNotFoundError(f"Cancellation {cancellation_id} not found")
        
        cancellation.complete_refund(transaction_id)
        
        self.session.flush()
        self.session.refresh(cancellation)
        
        return cancellation
    
    def fail_refund(
        self,
        cancellation_id: UUID,
        reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingCancellation:
        """
        Mark refund as failed.
        
        Args:
            cancellation_id: Cancellation UUID
            reason: Failure reason
            audit_context: Audit context
            
        Returns:
            Updated cancellation
        """
        cancellation = self.find_by_id(cancellation_id)
        if not cancellation:
            raise EntityNotFoundError(f"Cancellation {cancellation_id} not found")
        
        cancellation.fail_refund(reason)
        
        self.session.flush()
        self.session.refresh(cancellation)
        
        return cancellation
    
    def find_pending_refunds(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingCancellation]:
        """
        Find cancellations with pending refunds.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of cancellations with pending refunds
        """
        query = select(BookingCancellation).join(
            Booking,
            BookingCancellation.booking_id == Booking.id
        ).where(
            and_(
                BookingCancellation.request_refund == True,
                BookingCancellation.refund_status == PaymentStatus.PENDING,
                BookingCancellation.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.order_by(BookingCancellation.cancelled_at.asc()).options(
            joinedload(BookingCancellation.booking),
            joinedload(BookingCancellation.canceller),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_processing_refunds(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingCancellation]:
        """
        Find refunds currently being processed.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of refunds in processing
        """
        query = select(BookingCancellation).join(
            Booking,
            BookingCancellation.booking_id == Booking.id
        ).where(
            and_(
                BookingCancellation.refund_status == PaymentStatus.PROCESSING,
                BookingCancellation.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.order_by(BookingCancellation.refund_initiated_at.asc()).options(
            joinedload(BookingCancellation.booking),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_overdue_refunds(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingCancellation]:
        """
        Find refunds that are overdue (past expected completion date).
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of overdue refunds
        """
        query = select(BookingCancellation).join(
            Booking,
            BookingCancellation.booking_id == Booking.id
        ).where(
            and_(
                BookingCancellation.refund_status == PaymentStatus.PROCESSING,
                BookingCancellation.refund_initiated_at.isnot(None),
                BookingCancellation.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        # Filter for overdue (processing time exceeded)
        cancellations = self.session.execute(query).scalars().all()
        
        overdue = [
            c for c in cancellations
            if c.expected_refund_date and c.expected_refund_date < datetime.utcnow()
        ]
        
        return overdue
    
    def get_cancellation_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Get cancellation statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics dictionary
        """
        query = select(BookingCancellation).join(
            Booking,
            BookingCancellation.booking_id == Booking.id
        ).where(
            BookingCancellation.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(BookingCancellation.cancelled_at >= date_from)
        
        if date_to:
            query = query.where(BookingCancellation.cancelled_at <= date_to)
        
        cancellations = self.session.execute(query).scalars().all()
        
        total_cancellations = len(cancellations)
        
        # Refund statistics
        refund_requested = sum(1 for c in cancellations if c.request_refund)
        refunds_pending = sum(
            1 for c in cancellations
            if c.refund_status == PaymentStatus.PENDING
        )
        refunds_processing = sum(
            1 for c in cancellations
            if c.refund_status == PaymentStatus.PROCESSING
        )
        refunds_completed = sum(
            1 for c in cancellations
            if c.refund_status == PaymentStatus.COMPLETED
        )
        refunds_failed = sum(
            1 for c in cancellations
            if c.refund_status == PaymentStatus.FAILED
        )
        
        # Financial statistics
        total_advance_paid = sum(c.advance_paid for c in cancellations)
        total_charges = sum(c.cancellation_charge for c in cancellations)
        total_refundable = sum(c.refundable_amount for c in cancellations)
        
        avg_charge_percentage = (
            sum(c.cancellation_charge_percentage for c in cancellations) / total_cancellations
            if total_cancellations > 0 else Decimal("0.00")
        )
        
        # Group by canceller role
        by_role = {}
        for cancellation in cancellations:
            role = cancellation.cancelled_by_role
            by_role[role] = by_role.get(role, 0) + 1
        
        # Average days since cancellation
        avg_days_since = (
            sum(c.days_since_cancellation for c in cancellations) / total_cancellations
            if total_cancellations > 0 else 0
        )
        
        return {
            "total_cancellations": total_cancellations,
            "refund_requested": refund_requested,
            "refund_request_rate": (refund_requested / total_cancellations * 100) if total_cancellations > 0 else 0,
            "refunds_pending": refunds_pending,
            "refunds_processing": refunds_processing,
            "refunds_completed": refunds_completed,
            "refunds_failed": refunds_failed,
            "refund_completion_rate": (refunds_completed / refund_requested * 100) if refund_requested > 0 else 0,
            "total_advance_paid": total_advance_paid,
            "total_cancellation_charges": total_charges,
            "total_refundable_amount": total_refundable,
            "average_charge_percentage": avg_charge_percentage,
            "cancellations_by_role": by_role,
            "average_days_since_cancellation": avg_days_since,
        }


class CancellationPolicyRepository(BaseRepository[CancellationPolicy]):
    """Repository for cancellation policy management."""
    
    def __init__(self, session: Session):
        """Initialize policy repository."""
        super().__init__(session, CancellationPolicy)
    
    def find_by_hostel(
        self,
        hostel_id: UUID,
        include_inactive: bool = False,
    ) -> List[CancellationPolicy]:
        """
        Find cancellation policies for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            include_inactive: Whether to include inactive policies
            
        Returns:
            List of policies
        """
        query = select(CancellationPolicy).where(
            and_(
                CancellationPolicy.hostel_id == hostel_id,
                CancellationPolicy.deleted_at.is_(None),
            )
        )
        
        if not include_inactive:
            query = query.where(CancellationPolicy.is_active == True)
        
        query = query.order_by(CancellationPolicy.effective_from.desc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_active_by_hostel(
        self,
        hostel_id: UUID,
        as_of_date: Optional[datetime] = None,
    ) -> Optional[CancellationPolicy]:
        """
        Find currently active cancellation policy for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            as_of_date: Optional date to check (default: now)
            
        Returns:
            Active policy if found
        """
        check_date = as_of_date or datetime.utcnow()
        
        query = select(CancellationPolicy).where(
            and_(
                CancellationPolicy.hostel_id == hostel_id,
                CancellationPolicy.is_active == True,
                CancellationPolicy.effective_from <= check_date,
                or_(
                    CancellationPolicy.effective_until.is_(None),
                    CancellationPolicy.effective_until >= check_date,
                ),
                CancellationPolicy.deleted_at.is_(None),
            )
        ).order_by(CancellationPolicy.effective_from.desc())
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def create_or_update_policy(
        self,
        hostel_id: UUID,
        policy_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> CancellationPolicy:
        """
        Create new policy or update existing.
        
        Args:
            hostel_id: Hostel UUID
            policy_data: Policy data
            audit_context: Audit context
            
        Returns:
            Created or updated policy
        """
        # Deactivate existing active policies
        existing_policies = self.find_active_by_hostel(hostel_id)
        if existing_policies:
            existing_policies.is_active = False
            existing_policies.effective_until = datetime.utcnow()
        
        # Create new policy
        policy = CancellationPolicy(
            hostel_id=hostel_id,
            **policy_data,
        )
        
        return self.create(policy, audit_context)


class RefundTransactionRepository(BaseRepository[RefundTransaction]):
    """Repository for refund transaction tracking."""
    
    def __init__(self, session: Session):
        """Initialize refund transaction repository."""
        super().__init__(session, RefundTransaction)
    
    def create_refund_transaction(
        self,
        transaction_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> RefundTransaction:
        """
        Create refund transaction record.
        
        Args:
            transaction_data: Transaction data
            audit_context: Audit context
            
        Returns:
            Created transaction
        """
        transaction = RefundTransaction(**transaction_data)
        return self.create(transaction, audit_context)
    
    def find_by_cancellation(
        self,
        cancellation_id: UUID,
    ) -> List[RefundTransaction]:
        """
        Find refund transactions for a cancellation.
        
        Args:
            cancellation_id: Cancellation UUID
            
        Returns:
            List of refund transactions
        """
        query = select(RefundTransaction).where(
            RefundTransaction.cancellation_id == cancellation_id
        ).order_by(RefundTransaction.initiated_at.desc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_by_gateway_id(
        self,
        gateway_transaction_id: str,
    ) -> Optional[RefundTransaction]:
        """
        Find refund transaction by gateway transaction ID.
        
        Args:
            gateway_transaction_id: Gateway transaction ID
            
        Returns:
            Refund transaction if found
        """
        query = select(RefundTransaction).where(
            RefundTransaction.gateway_transaction_id == gateway_transaction_id
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()