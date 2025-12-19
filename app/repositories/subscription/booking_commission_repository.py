"""
Booking Commission Repository.

Manages commission tracking for bookings made through
subscription system.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.subscription.booking_commission import BookingCommission
from app.schemas.subscription.commission import CommissionStatus


class BookingCommissionRepository:
    """
    Repository for booking commission operations.

    Provides methods for commission tracking, payment processing,
    and commission analytics.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ==================== CREATE OPERATIONS ====================

    def create_commission(
        self,
        commission_data: Dict[str, Any],
    ) -> BookingCommission:
        """
        Create new commission record.

        Args:
            commission_data: Commission configuration data

        Returns:
            Created commission record
        """
        commission = BookingCommission(**commission_data)
        self.db.add(commission)
        self.db.flush()
        return commission

    def create_booking_commission(
        self,
        booking_id: UUID,
        hostel_id: UUID,
        subscription_id: UUID,
        booking_amount: Decimal,
        commission_percentage: Decimal,
        due_days: int = 30,
        currency: str = "INR",
    ) -> BookingCommission:
        """
        Create commission for booking.

        Args:
            booking_id: Booking ID
            hostel_id: Hostel ID
            subscription_id: Subscription ID
            booking_amount: Total booking amount
            commission_percentage: Commission percentage
            due_days: Days until payment due
            currency: Currency code

        Returns:
            Created commission record
        """
        commission_amount = (booking_amount * commission_percentage / 100).quantize(
            Decimal("0.01")
        )
        
        due_date = date.today() + timedelta(days=due_days)
        
        commission_data = {
            "booking_id": booking_id,
            "hostel_id": hostel_id,
            "subscription_id": subscription_id,
            "booking_amount": booking_amount,
            "commission_percentage": commission_percentage,
            "commission_amount": commission_amount,
            "currency": currency,
            "status": CommissionStatus.PENDING,
            "due_date": due_date,
        }
        
        return self.create_commission(commission_data)

    # ==================== READ OPERATIONS ====================

    def get_by_id(
        self,
        commission_id: UUID,
    ) -> Optional[BookingCommission]:
        """
        Get commission by ID.

        Args:
            commission_id: Commission ID

        Returns:
            Commission if found
        """
        query = (
            select(BookingCommission)
            .where(BookingCommission.id == commission_id)
            .options(joinedload(BookingCommission.subscription))
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_by_booking(
        self,
        booking_id: UUID,
    ) -> Optional[BookingCommission]:
        """
        Get commission for booking.

        Args:
            booking_id: Booking ID

        Returns:
            Commission if found
        """
        query = (
            select(BookingCommission)
            .where(BookingCommission.booking_id == booking_id)
            .options(joinedload(BookingCommission.subscription))
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_by_hostel(
        self,
        hostel_id: UUID,
        status: Optional[CommissionStatus] = None,
        limit: Optional[int] = None,
    ) -> List[BookingCommission]:
        """
        Get commissions for hostel.

        Args:
            hostel_id: Hostel ID
            status: Filter by commission status
            limit: Maximum number of results

        Returns:
            List of commissions
        """
        query = (
            select(BookingCommission)
            .where(BookingCommission.hostel_id == hostel_id)
            .options(joinedload(BookingCommission.subscription))
            .order_by(BookingCommission.created_at.desc())
        )
        
        if status:
            query = query.where(BookingCommission.status == status)
        
        if limit:
            query = query.limit(limit)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_by_subscription(
        self,
        subscription_id: UUID,
        status: Optional[CommissionStatus] = None,
    ) -> List[BookingCommission]:
        """
        Get commissions for subscription.

        Args:
            subscription_id: Subscription ID
            status: Filter by commission status

        Returns:
            List of commissions
        """
        query = (
            select(BookingCommission)
            .where(BookingCommission.subscription_id == subscription_id)
            .options(joinedload(BookingCommission.subscription))
            .order_by(BookingCommission.created_at.desc())
        )
        
        if status:
            query = query.where(BookingCommission.status == status)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_by_status(
        self,
        status: CommissionStatus,
        limit: Optional[int] = None,
    ) -> List[BookingCommission]:
        """
        Get commissions by status.

        Args:
            status: Commission status
            limit: Maximum number of results

        Returns:
            List of commissions
        """
        query = (
            select(BookingCommission)
            .where(BookingCommission.status == status)
            .options(joinedload(BookingCommission.subscription))
            .order_by(BookingCommission.created_at.desc())
        )
        
        if limit:
            query = query.limit(limit)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_pending_commissions(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingCommission]:
        """
        Get all pending commissions.

        Args:
            hostel_id: Optional hostel ID filter

        Returns:
            List of pending commissions
        """
        query = (
            select(BookingCommission)
            .where(BookingCommission.status == CommissionStatus.PENDING)
            .options(joinedload(BookingCommission.subscription))
            .order_by(BookingCommission.due_date)
        )
        
        if hostel_id:
            query = query.where(BookingCommission.hostel_id == hostel_id)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_overdue_commissions(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingCommission]:
        """
        Get overdue commissions.

        Args:
            hostel_id: Optional hostel ID filter

        Returns:
            List of overdue commissions
        """
        today = date.today()
        
        query = (
            select(BookingCommission)
            .where(
                and_(
                    BookingCommission.status.in_([
                        CommissionStatus.PENDING,
                        CommissionStatus.PROCESSING,
                    ]),
                    BookingCommission.due_date < today,
                )
            )
            .options(joinedload(BookingCommission.subscription))
            .order_by(BookingCommission.due_date)
        )
        
        if hostel_id:
            query = query.where(BookingCommission.hostel_id == hostel_id)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_due_soon(
        self,
        days: int = 7,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingCommission]:
        """
        Get commissions due within specified days.

        Args:
            days: Number of days to look ahead
            hostel_id: Optional hostel ID filter

        Returns:
            List of commissions due soon
        """
        today = date.today()
        end_date = today + timedelta(days=days)
        
        query = (
            select(BookingCommission)
            .where(
                and_(
                    BookingCommission.status == CommissionStatus.PENDING,
                    BookingCommission.due_date >= today,
                    BookingCommission.due_date <= end_date,
                )
            )
            .options(joinedload(BookingCommission.subscription))
            .order_by(BookingCommission.due_date)
        )
        
        if hostel_id:
            query = query.where(BookingCommission.hostel_id == hostel_id)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_paid_commissions(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[BookingCommission]:
        """
        Get paid commissions.

        Args:
            hostel_id: Optional hostel ID filter
            start_date: Filter by payment date start
            end_date: Filter by payment date end

        Returns:
            List of paid commissions
        """
        query = (
            select(BookingCommission)
            .where(BookingCommission.status == CommissionStatus.PAID)
            .options(joinedload(BookingCommission.subscription))
            .order_by(BookingCommission.paid_date.desc())
        )
        
        if hostel_id:
            query = query.where(BookingCommission.hostel_id == hostel_id)
        
        if start_date:
            query = query.where(BookingCommission.paid_date >= start_date)
        
        if end_date:
            query = query.where(BookingCommission.paid_date <= end_date)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    # ==================== UPDATE OPERATIONS ====================

    def update_commission(
        self,
        commission_id: UUID,
        update_data: Dict[str, Any],
    ) -> Optional[BookingCommission]:
        """
        Update commission details.

        Args:
            commission_id: Commission ID
            update_data: Updated data

        Returns:
            Updated commission
        """
        commission = self.get_by_id(commission_id)
        if not commission:
            return None
        
        for key, value in update_data.items():
            if hasattr(commission, key):
                setattr(commission, key, value)
        
        commission.updated_at = datetime.utcnow()
        self.db.flush()
        return commission

    def update_status(
        self,
        commission_id: UUID,
        status: CommissionStatus,
    ) -> Optional[BookingCommission]:
        """
        Update commission status.

        Args:
            commission_id: Commission ID
            status: New status

        Returns:
            Updated commission
        """
        commission = self.get_by_id(commission_id)
        if not commission:
            return None
        
        commission.status = status
        commission.updated_at = datetime.utcnow()
        
        self.db.flush()
        return commission

    def mark_as_processing(
        self,
        commission_id: UUID,
    ) -> Optional[BookingCommission]:
        """
        Mark commission as processing.

        Args:
            commission_id: Commission ID

        Returns:
            Updated commission
        """
        return self.update_status(commission_id, CommissionStatus.PROCESSING)

    def mark_as_paid(
        self,
        commission_id: UUID,
        paid_date: Optional[date] = None,
        payment_reference: Optional[str] = None,
    ) -> Optional[BookingCommission]:
        """
        Mark commission as paid.

        Args:
            commission_id: Commission ID
            paid_date: Payment date
            payment_reference: Payment reference

        Returns:
            Updated commission
        """
        commission = self.get_by_id(commission_id)
        if not commission:
            return None
        
        commission.status = CommissionStatus.PAID
        commission.paid_date = paid_date or date.today()
        commission.payment_reference = payment_reference
        commission.updated_at = datetime.utcnow()
        
        self.db.flush()
        return commission

    def mark_as_cancelled(
        self,
        commission_id: UUID,
        reason: Optional[str] = None,
    ) -> Optional[BookingCommission]:
        """
        Mark commission as cancelled.

        Args:
            commission_id: Commission ID
            reason: Cancellation reason

        Returns:
            Updated commission
        """
        commission = self.get_by_id(commission_id)
        if not commission:
            return None
        
        commission.status = CommissionStatus.CANCELLED
        commission.updated_at = datetime.utcnow()
        
        self.db.flush()
        return commission

    def mark_as_refunded(
        self,
        commission_id: UUID,
        refund_date: Optional[date] = None,
        refund_reference: Optional[str] = None,
    ) -> Optional[BookingCommission]:
        """
        Mark commission as refunded.

        Args:
            commission_id: Commission ID
            refund_date: Refund date
            refund_reference: Refund reference

        Returns:
            Updated commission
        """
        commission = self.get_by_id(commission_id)
        if not commission:
            return None
        
        commission.status = CommissionStatus.REFUNDED
        commission.paid_date = refund_date or date.today()
        commission.payment_reference = refund_reference
        commission.updated_at = datetime.utcnow()
        
        self.db.flush()
        return commission

    def extend_due_date(
        self,
        commission_id: UUID,
        new_due_date: date,
    ) -> Optional[BookingCommission]:
        """
        Extend commission due date.

        Args:
            commission_id: Commission ID
            new_due_date: New due date

        Returns:
            Updated commission
        """
        commission = self.get_by_id(commission_id)
        if not commission:
            return None
        
        commission.due_date = new_due_date
        commission.updated_at = datetime.utcnow()
        
        self.db.flush()
        return commission

    # ==================== DELETE OPERATIONS ====================

    def delete_commission(
        self,
        commission_id: UUID,
    ) -> bool:
        """
        Delete commission (hard delete).

        Args:
            commission_id: Commission ID

        Returns:
            True if deleted
        """
        commission = self.get_by_id(commission_id)
        if not commission:
            return False
        
        # Only allow deletion of cancelled commissions
        if commission.status != CommissionStatus.CANCELLED:
            return False
        
        self.db.delete(commission)
        self.db.flush()
        return True

    # ==================== ANALYTICS & REPORTING ====================

    def get_commission_statistics(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Get commission statistics.

        Args:
            hostel_id: Optional hostel ID filter

        Returns:
            Dictionary with commission statistics
        """
        query = select(BookingCommission)
        
        if hostel_id:
            query = query.where(BookingCommission.hostel_id == hostel_id)
        
        result = self.db.execute(query)
        commissions = list(result.scalars().all())
        
        total_commissions = len(commissions)
        pending_commissions = sum(
            1 for c in commissions if c.status == CommissionStatus.PENDING
        )
        paid_commissions = sum(
            1 for c in commissions if c.status == CommissionStatus.PAID
        )
        overdue_commissions = sum(1 for c in commissions if c.is_overdue)
        
        total_amount = sum(c.commission_amount for c in commissions)
        pending_amount = sum(
            c.commission_amount
            for c in commissions
            if c.status == CommissionStatus.PENDING
        )
        paid_amount = sum(
            c.commission_amount
            for c in commissions
            if c.status == CommissionStatus.PAID
        )
        overdue_amount = sum(c.commission_amount for c in commissions if c.is_overdue)
        
        return {
            "total_commissions": total_commissions,
            "pending_commissions": pending_commissions,
            "paid_commissions": paid_commissions,
            "overdue_commissions": overdue_commissions,
            "total_commission_amount": float(total_amount),
            "pending_amount": float(pending_amount),
            "paid_amount": float(paid_amount),
            "overdue_amount": float(overdue_amount),
            "collection_rate": (
                float(paid_commissions / total_commissions * 100)
                if total_commissions > 0
                else 0
            ),
        }

    def get_commission_by_period(
        self,
        start_date: date,
        end_date: date,
        hostel_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Get commission statistics for period.

        Args:
            start_date: Period start date
            end_date: Period end date
            hostel_id: Optional hostel ID filter

        Returns:
            Commission statistics for period
        """
        query = select(BookingCommission).where(
            and_(
                BookingCommission.created_at >= start_date,
                BookingCommission.created_at <= end_date,
            )
        )
        
        if hostel_id:
            query = query.where(BookingCommission.hostel_id == hostel_id)
        
        result = self.db.execute(query)
        commissions = list(result.scalars().all())
        
        total_commission = sum(c.commission_amount for c in commissions)
        paid_commission = sum(
            c.commission_amount
            for c in commissions
            if c.status == CommissionStatus.PAID
        )
        booking_count = len(commissions)
        
        avg_commission = (
            total_commission / booking_count if booking_count > 0 else Decimal("0.00")
        )
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "total_bookings": booking_count,
            "total_commission": float(total_commission),
            "paid_commission": float(paid_commission),
            "pending_commission": float(total_commission - paid_commission),
            "average_commission": float(avg_commission),
        }

    def get_outstanding_by_hostel(
        self,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get outstanding commission summary for hostel.

        Args:
            hostel_id: Hostel ID

        Returns:
            Outstanding commission summary
        """
        pending = self.get_pending_commissions(hostel_id)
        overdue = [c for c in pending if c.is_overdue]
        
        total_outstanding = sum(c.commission_amount for c in pending)
        overdue_amount = sum(c.commission_amount for c in overdue)
        
        oldest_pending = min(
            (c.created_at for c in pending),
            default=None
        )
        
        return {
            "hostel_id": str(hostel_id),
            "total_outstanding": float(total_outstanding),
            "overdue_amount": float(overdue_amount),
            "pending_count": len(pending),
            "overdue_count": len(overdue),
            "oldest_pending": oldest_pending.isoformat() if oldest_pending else None,
        }

    # ==================== BATCH OPERATIONS ====================

    def batch_mark_as_paid(
        self,
        commission_ids: List[UUID],
        paid_date: Optional[date] = None,
        payment_reference: Optional[str] = None,
    ) -> int:
        """
        Batch mark commissions as paid.

        Args:
            commission_ids: List of commission IDs
            paid_date: Payment date
            payment_reference: Payment reference

        Returns:
            Number of commissions marked as paid
        """
        count = 0
        for commission_id in commission_ids:
            if self.mark_as_paid(commission_id, paid_date, payment_reference):
                count += 1
        return count

    def batch_extend_due_date(
        self,
        commission_ids: List[UUID],
        new_due_date: date,
    ) -> int:
        """
        Batch extend due dates.

        Args:
            commission_ids: List of commission IDs
            new_due_date: New due date

        Returns:
            Number of commissions updated
        """
        count = 0
        for commission_id in commission_ids:
            if self.extend_due_date(commission_id, new_due_date):
                count += 1
        return count

    # ==================== SEARCH & FILTERING ====================

    def search_commissions(
        self,
        hostel_id: Optional[UUID] = None,
        subscription_id: Optional[UUID] = None,
        status: Optional[CommissionStatus] = None,
        created_from: Optional[date] = None,
        created_to: Optional[date] = None,
        due_date_from: Optional[date] = None,
        due_date_to: Optional[date] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[BookingCommission]:
        """
        Search commissions with multiple filters.

        Args:
            hostel_id: Filter by hostel
            subscription_id: Filter by subscription
            status: Filter by status
            created_from: Created date range start
            created_to: Created date range end
            due_date_from: Due date range start
            due_date_to: Due date range end
            min_amount: Minimum commission amount
            max_amount: Maximum commission amount
            limit: Maximum results
            offset: Results offset

        Returns:
            List of matching commissions
        """
        query = select(BookingCommission).options(
            joinedload(BookingCommission.subscription)
        )
        
        conditions = []
        
        if hostel_id:
            conditions.append(BookingCommission.hostel_id == hostel_id)
        
        if subscription_id:
            conditions.append(BookingCommission.subscription_id == subscription_id)
        
        if status:
            conditions.append(BookingCommission.status == status)
        
        if created_from:
            conditions.append(BookingCommission.created_at >= created_from)
        
        if created_to:
            conditions.append(BookingCommission.created_at <= created_to)
        
        if due_date_from:
            conditions.append(BookingCommission.due_date >= due_date_from)
        
        if due_date_to:
            conditions.append(BookingCommission.due_date <= due_date_to)
        
        if min_amount is not None:
            conditions.append(BookingCommission.commission_amount >= min_amount)
        
        if max_amount is not None:
            conditions.append(BookingCommission.commission_amount <= max_amount)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(BookingCommission.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        if offset:
            query = query.offset(offset)
        
        result = self.db.execute(query)
        return list(result.scalars().all())