# app/repositories/booking/booking_approval_repository.py
"""
Booking approval repository for approval workflow management.

Provides approval decision tracking, settings management, rejection handling,
and auto-approval logic.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import EntityNotFoundError, ValidationError
from app.models.booking.booking_approval import (
    ApprovalSettings,
    BookingApproval,
    RejectionRecord,
)
from app.models.booking.booking import Booking
from app.models.base.enums import BookingStatus
from app.repositories.base.base_repository import (
    AuditContext,
    BaseRepository,
    QueryOptions,
)


class BookingApprovalRepository(BaseRepository[BookingApproval]):
    """
    Repository for booking approval operations.
    
    Provides:
    - Approval workflow management
    - Auto-approval logic
    - Rejection tracking
    - Approval settings configuration
    - Payment requirement calculation
    """
    
    def __init__(self, session: Session):
        """Initialize approval repository."""
        super().__init__(session, BookingApproval)
    
    # ==================== APPROVAL OPERATIONS ====================
    
    def create_approval_record(
        self,
        booking_id: UUID,
        approval_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingApproval:
        """
        Create approval record for a booking.
        
        Args:
            booking_id: Booking UUID
            approval_data: Approval information
            audit_context: Audit context
            
        Returns:
            Created approval record
        """
        # Calculate advance payment amount if not provided
        if 'advance_payment_amount' not in approval_data:
            total_amount = approval_data.get('total_amount', Decimal("0.00"))
            percentage = approval_data.get('advance_payment_percentage', Decimal("20.00"))
            approval_data['advance_payment_amount'] = (total_amount * percentage / 100).quantize(
                Decimal("0.01")
            )
        
        approval = BookingApproval(
            booking_id=booking_id,
            approved_by=audit_context.user_id if audit_context else None,
            approved_at=datetime.utcnow(),
            **approval_data,
        )
        
        return self.create(approval, audit_context)
    
    def find_by_booking(self, booking_id: UUID) -> Optional[BookingApproval]:
        """
        Find approval record for a booking.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Approval record if found
        """
        query = select(BookingApproval).where(
            BookingApproval.booking_id == booking_id
        ).where(
            BookingApproval.deleted_at.is_(None)
        ).options(
            joinedload(BookingApproval.booking),
            joinedload(BookingApproval.approver),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def update_pricing(
        self,
        booking_id: UUID,
        pricing_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingApproval:
        """
        Update pricing in approval record.
        
        Args:
            booking_id: Booking UUID
            pricing_data: Updated pricing information
            audit_context: Audit context
            
        Returns:
            Updated approval record
        """
        approval = self.find_by_booking(booking_id)
        if not approval:
            raise EntityNotFoundError(f"Approval for booking {booking_id} not found")
        
        # Recalculate advance amount if percentage changed
        if 'advance_payment_percentage' in pricing_data or 'total_amount' in pricing_data:
            total = pricing_data.get('total_amount', approval.total_amount)
            percentage = pricing_data.get(
                'advance_payment_percentage',
                approval.advance_payment_percentage
            )
            pricing_data['advance_payment_amount'] = (total * percentage / 100).quantize(
                Decimal("0.01")
            )
        
        # Update fields
        for key, value in pricing_data.items():
            if hasattr(approval, key):
                setattr(approval, key, value)
        
        self.session.flush()
        self.session.refresh(approval)
        
        return approval
    
    def set_payment_deadline(
        self,
        booking_id: UUID,
        deadline_hours: int = 72,
    ) -> BookingApproval:
        """
        Set advance payment deadline.
        
        Args:
            booking_id: Booking UUID
            deadline_hours: Hours from now for deadline
            
        Returns:
            Updated approval record
        """
        approval = self.find_by_booking(booking_id)
        if not approval:
            raise EntityNotFoundError(f"Approval for booking {booking_id} not found")
        
        approval.advance_payment_deadline = datetime.utcnow() + timedelta(hours=deadline_hours)
        
        self.session.flush()
        self.session.refresh(approval)
        
        return approval
    
    def mark_notification_sent(
        self,
        booking_id: UUID,
    ) -> BookingApproval:
        """
        Mark approval notification as sent.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Updated approval record
        """
        approval = self.find_by_booking(booking_id)
        if not approval:
            raise EntityNotFoundError(f"Approval for booking {booking_id} not found")
        
        approval.send_approval_notification()
        
        self.session.flush()
        self.session.refresh(approval)
        
        return approval
    
    def find_pending_payment(
        self,
        hostel_id: Optional[UUID] = None,
        overdue_only: bool = False,
    ) -> List[BookingApproval]:
        """
        Find approvals with pending advance payment.
        
        Args:
            hostel_id: Optional hostel filter
            overdue_only: If True, only return overdue payments
            
        Returns:
            List of approvals with pending payment
        """
        query = select(BookingApproval).join(
            Booking,
            BookingApproval.booking_id == Booking.id
        ).where(
            and_(
                BookingApproval.advance_payment_required == True,
                Booking.advance_paid == False,
                Booking.booking_status == BookingStatus.APPROVED,
                BookingApproval.deleted_at.is_(None),
                Booking.deleted_at.is_(None),
            )
        )
        
        if overdue_only:
            query = query.where(
                and_(
                    BookingApproval.advance_payment_deadline.isnot(None),
                    BookingApproval.advance_payment_deadline < datetime.utcnow()
                )
            )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.order_by(BookingApproval.advance_payment_deadline.asc()).options(
            joinedload(BookingApproval.booking),
            joinedload(BookingApproval.approver),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_payment_expiring_soon(
        self,
        within_hours: int = 24,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingApproval]:
        """
        Find approvals with payment deadline expiring soon.
        
        Args:
            within_hours: Hours threshold
            hostel_id: Optional hostel filter
            
        Returns:
            List of approvals with expiring deadlines
        """
        expiry_threshold = datetime.utcnow() + timedelta(hours=within_hours)
        
        query = select(BookingApproval).join(
            Booking,
            BookingApproval.booking_id == Booking.id
        ).where(
            and_(
                BookingApproval.advance_payment_required == True,
                Booking.advance_paid == False,
                BookingApproval.advance_payment_deadline.isnot(None),
                BookingApproval.advance_payment_deadline > datetime.utcnow(),
                BookingApproval.advance_payment_deadline <= expiry_threshold,
                BookingApproval.deleted_at.is_(None),
                Booking.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.order_by(BookingApproval.advance_payment_deadline.asc()).options(
            joinedload(BookingApproval.booking),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_auto_approved(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[BookingApproval]:
        """
        Find auto-approved bookings.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            List of auto-approved bookings
        """
        query = select(BookingApproval).join(
            Booking,
            BookingApproval.booking_id == Booking.id
        ).where(
            and_(
                BookingApproval.auto_approved == True,
                BookingApproval.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(BookingApproval.approved_at >= date_from)
        
        if date_to:
            query = query.where(BookingApproval.approved_at <= date_to)
        
        query = query.order_by(BookingApproval.approved_at.desc()).options(
            joinedload(BookingApproval.booking),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_approval_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Get approval statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics dictionary
        """
        query = select(BookingApproval).join(
            Booking,
            BookingApproval.booking_id == Booking.id
        ).where(
            BookingApproval.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(BookingApproval.approved_at >= date_from)
        
        if date_to:
            query = query.where(BookingApproval.approved_at <= date_to)
        
        approvals = self.session.execute(query).scalars().all()
        
        total_approvals = len(approvals)
        auto_approved = sum(1 for a in approvals if a.auto_approved)
        manual_approved = total_approvals - auto_approved
        
        payment_required = sum(1 for a in approvals if a.advance_payment_required)
        
        total_revenue = sum(a.total_amount for a in approvals)
        avg_booking_value = total_revenue / total_approvals if total_approvals > 0 else Decimal("0.00")
        
        avg_advance_percentage = (
            sum(a.advance_payment_percentage for a in approvals) / total_approvals
            if total_approvals > 0 else Decimal("0.00")
        )
        
        return {
            "total_approvals": total_approvals,
            "auto_approved": auto_approved,
            "manual_approved": manual_approved,
            "auto_approval_rate": (auto_approved / total_approvals * 100) if total_approvals > 0 else 0,
            "payment_required_count": payment_required,
            "total_revenue": total_revenue,
            "average_booking_value": avg_booking_value,
            "average_advance_percentage": avg_advance_percentage,
        }


class ApprovalSettingsRepository(BaseRepository[ApprovalSettings]):
    """Repository for approval settings management."""
    
    def __init__(self, session: Session):
        """Initialize approval settings repository."""
        super().__init__(session, ApprovalSettings)
    
    def find_by_hostel(self, hostel_id: UUID) -> Optional[ApprovalSettings]:
        """
        Find approval settings for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Approval settings if found
        """
        query = select(ApprovalSettings).where(
            ApprovalSettings.hostel_id == hostel_id
        ).where(
            ApprovalSettings.deleted_at.is_(None)
        ).options(
            joinedload(ApprovalSettings.hostel),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def create_or_update_settings(
        self,
        hostel_id: UUID,
        settings_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> ApprovalSettings:
        """
        Create or update approval settings for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            settings_data: Settings data
            audit_context: Audit context
            
        Returns:
            Created or updated settings
        """
        existing = self.find_by_hostel(hostel_id)
        
        if existing:
            # Update existing
            for key, value in settings_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            
            if audit_context:
                existing.last_updated_by = audit_context.user_id
            
            self.session.flush()
            self.session.refresh(existing)
            return existing
        else:
            # Create new
            settings = ApprovalSettings(
                hostel_id=hostel_id,
                last_updated_by=audit_context.user_id if audit_context else None,
                **settings_data,
            )
            return self.create(settings, audit_context)
    
    def check_auto_approval_criteria(
        self,
        hostel_id: UUID,
        booking_data: Dict,
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if booking meets auto-approval criteria.
        
        Args:
            hostel_id: Hostel UUID
            booking_data: Booking information to check
            
        Returns:
            Tuple of (should_auto_approve, criteria_met)
        """
        settings = self.find_by_hostel(hostel_id)
        
        if not settings or not settings.auto_approve_enabled:
            return False, None
        
        if not settings.auto_approve_conditions:
            return False, None
        
        conditions = settings.auto_approve_conditions
        criteria_met = {}
        
        # Check each condition
        for condition_key, condition_value in conditions.items():
            if condition_key == "max_booking_amount":
                booking_amount = booking_data.get("total_amount", Decimal("0.00"))
                meets_criteria = booking_amount <= Decimal(str(condition_value))
                criteria_met[condition_key] = meets_criteria
                if not meets_criteria:
                    return False, criteria_met
            
            elif condition_key == "min_stay_duration":
                duration = booking_data.get("stay_duration_months", 0)
                meets_criteria = duration >= condition_value
                criteria_met[condition_key] = meets_criteria
                if not meets_criteria:
                    return False, criteria_met
            
            elif condition_key == "allowed_room_types":
                room_type = booking_data.get("room_type_requested")
                meets_criteria = str(room_type) in condition_value
                criteria_met[condition_key] = meets_criteria
                if not meets_criteria:
                    return False, criteria_met
            
            elif condition_key == "require_advance_payment":
                meets_criteria = condition_value is True
                criteria_met[condition_key] = meets_criteria
        
        return True, criteria_met
    
    def find_hostels_with_auto_approval(self) -> List[ApprovalSettings]:
        """
        Find all hostels with auto-approval enabled.
        
        Returns:
            List of approval settings with auto-approval enabled
        """
        query = select(ApprovalSettings).where(
            and_(
                ApprovalSettings.auto_approve_enabled == True,
                ApprovalSettings.deleted_at.is_(None),
            )
        ).options(
            joinedload(ApprovalSettings.hostel),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())


class RejectionRecordRepository(BaseRepository[RejectionRecord]):
    """Repository for booking rejection tracking."""
    
    def __init__(self, session: Session):
        """Initialize rejection record repository."""
        super().__init__(session, RejectionRecord)
    
    def create_rejection_record(
        self,
        booking_id: UUID,
        rejection_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> RejectionRecord:
        """
        Create rejection record for a booking.
        
        Args:
            booking_id: Booking UUID
            rejection_data: Rejection information
            audit_context: Audit context
            
        Returns:
            Created rejection record
        """
        record = RejectionRecord(
            booking_id=booking_id,
            rejected_by=audit_context.user_id if audit_context else None,
            rejected_at=datetime.utcnow(),
            **rejection_data,
        )
        
        return self.create(record, audit_context)
    
    def find_by_booking(self, booking_id: UUID) -> Optional[RejectionRecord]:
        """
        Find rejection record for a booking.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Rejection record if found
        """
        query = select(RejectionRecord).where(
            RejectionRecord.booking_id == booking_id
        ).where(
            RejectionRecord.deleted_at.is_(None)
        ).options(
            joinedload(RejectionRecord.booking),
            joinedload(RejectionRecord.rejecter),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def mark_notification_sent(self, booking_id: UUID) -> RejectionRecord:
        """
        Mark rejection notification as sent.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Updated rejection record
        """
        record = self.find_by_booking(booking_id)
        if not record:
            raise EntityNotFoundError(f"Rejection record for booking {booking_id} not found")
        
        record.send_rejection_notification()
        
        self.session.flush()
        self.session.refresh(record)
        
        return record
    
    def find_with_alternatives_suggested(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[RejectionRecord]:
        """
        Find rejections where alternatives were suggested.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            List of rejection records with alternatives
        """
        query = select(RejectionRecord).join(
            Booking,
            RejectionRecord.booking_id == Booking.id
        ).where(
            and_(
                or_(
                    RejectionRecord.suggest_alternative_dates == True,
                    RejectionRecord.suggest_alternative_room_types == True,
                ),
                RejectionRecord.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(RejectionRecord.rejected_at >= date_from)
        
        if date_to:
            query = query.where(RejectionRecord.rejected_at <= date_to)
        
        query = query.order_by(RejectionRecord.rejected_at.desc()).options(
            joinedload(RejectionRecord.booking),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_rejection_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Get rejection statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics dictionary
        """
        query = select(RejectionRecord).join(
            Booking,
            RejectionRecord.booking_id == Booking.id
        ).where(
            RejectionRecord.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(RejectionRecord.rejected_at >= date_from)
        
        if date_to:
            query = query.where(RejectionRecord.rejected_at <= date_to)
        
        rejections = self.session.execute(query).scalars().all()
        
        total_rejections = len(rejections)
        
        with_date_alternatives = sum(
            1 for r in rejections if r.suggest_alternative_dates
        )
        with_room_alternatives = sum(
            1 for r in rejections if r.suggest_alternative_room_types
        )
        notifications_sent = sum(
            1 for r in rejections if r.rejection_notification_sent
        )
        
        # Group by rejection reason (first 50 chars)
        reason_groups = {}
        for rejection in rejections:
            reason_key = rejection.rejection_reason[:50] if rejection.rejection_reason else "Unknown"
            reason_groups[reason_key] = reason_groups.get(reason_key, 0) + 1
        
        return {
            "total_rejections": total_rejections,
            "with_date_alternatives": with_date_alternatives,
            "with_room_alternatives": with_room_alternatives,
            "alternatives_suggested_rate": (
                (with_date_alternatives + with_room_alternatives) / total_rejections * 100
                if total_rejections > 0 else 0
            ),
            "notifications_sent": notifications_sent,
            "notification_rate": (
                notifications_sent / total_rejections * 100
                if total_rejections > 0 else 0
            ),
            "top_rejection_reasons": sorted(
                reason_groups.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
        }