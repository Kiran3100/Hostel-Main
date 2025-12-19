# --- File: payment_repository.py ---
"""
Payment Repository.

Comprehensive payment processing with multi-gateway support, 
fraud detection, and financial compliance.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payment.payment import Payment
from app.repositories.base.base_repository import BaseRepository
from app.schemas.common.enums import PaymentMethod, PaymentStatus, PaymentType


class PaymentRepository(BaseRepository[Payment]):
    """Repository for payment operations."""

    def __init__(self, session: AsyncSession):
        """Initialize payment repository."""
        super().__init__(Payment, session)

    # ==================== Core Payment Operations ====================

    async def create_payment(
        self,
        hostel_id: UUID,
        payer_id: UUID,
        payment_type: PaymentType,
        amount: Decimal,
        payment_method: PaymentMethod,
        student_id: UUID | None = None,
        booking_id: UUID | None = None,
        payment_schedule_id: UUID | None = None,
        due_date: date | None = None,
        metadata: dict | None = None,
    ) -> Payment:
        """
        Create a new payment record.
        
        Args:
            hostel_id: Hostel ID
            payer_id: User ID who is paying
            payment_type: Type of payment
            amount: Payment amount
            payment_method: Payment method
            student_id: Optional student ID
            booking_id: Optional booking ID
            payment_schedule_id: Optional payment schedule ID
            due_date: Optional due date
            metadata: Additional metadata
            
        Returns:
            Created payment
        """
        # Generate unique payment reference
        payment_reference = await self._generate_payment_reference(hostel_id)
        
        payment_data = {
            "hostel_id": hostel_id,
            "payer_id": payer_id,
            "student_id": student_id,
            "booking_id": booking_id,
            "payment_schedule_id": payment_schedule_id,
            "payment_reference": payment_reference,
            "payment_type": payment_type,
            "amount": amount,
            "payment_method": payment_method,
            "payment_status": PaymentStatus.PENDING,
            "due_date": due_date,
            "metadata": metadata or {},
        }
        
        return await self.create(payment_data)

    async def process_payment_transaction(
        self,
        payment_id: UUID,
        transaction_id: str,
        gateway_order_id: str | None = None,
        gateway_response: dict | None = None,
    ) -> Payment:
        """
        Process payment transaction and update status.
        
        Args:
            payment_id: Payment ID
            transaction_id: Gateway transaction ID
            gateway_order_id: Gateway order ID
            gateway_response: Gateway response data
            
        Returns:
            Updated payment
        """
        payment = await self.get_by_id(payment_id)
        if not payment:
            raise ValueError(f"Payment not found: {payment_id}")
        
        update_data = {
            "transaction_id": transaction_id,
            "gateway_order_id": gateway_order_id,
            "gateway_response": gateway_response,
            "payment_status": PaymentStatus.PROCESSING,
        }
        
        return await self.update(payment_id, update_data)

    async def mark_payment_completed(
        self,
        payment_id: UUID,
        collected_by: UUID | None = None,
        receipt_number: str | None = None,
    ) -> Payment:
        """
        Mark payment as completed.
        
        Args:
            payment_id: Payment ID
            collected_by: Staff who collected payment (for offline)
            receipt_number: Receipt number
            
        Returns:
            Updated payment
        """
        now = datetime.utcnow()
        
        update_data = {
            "payment_status": PaymentStatus.COMPLETED,
            "paid_at": now,
            "collected_by": collected_by,
            "receipt_number": receipt_number or await self._generate_receipt_number(payment_id),
            "receipt_generated_at": now,
        }
        
        return await self.update(payment_id, update_data)

    async def mark_payment_failed(
        self,
        payment_id: UUID,
        failure_reason: str,
    ) -> Payment:
        """
        Mark payment as failed.
        
        Args:
            payment_id: Payment ID
            failure_reason: Reason for failure
            
        Returns:
            Updated payment
        """
        update_data = {
            "payment_status": PaymentStatus.FAILED,
            "failed_at": datetime.utcnow(),
            "failure_reason": failure_reason,
        }
        
        return await self.update(payment_id, update_data)

    async def handle_payment_refund(
        self,
        payment_id: UUID,
        refund_amount: Decimal,
    ) -> Payment:
        """
        Update payment with refund information.
        
        Args:
            payment_id: Payment ID
            refund_amount: Amount refunded
            
        Returns:
            Updated payment
        """
        payment = await self.get_by_id(payment_id)
        if not payment:
            raise ValueError(f"Payment not found: {payment_id}")
        
        total_refund = payment.refund_amount + refund_amount
        
        update_data = {
            "refund_amount": total_refund,
            "is_refunded": total_refund > Decimal("0"),
        }
        
        return await self.update(payment_id, update_data)

    # ==================== Query Methods ====================

    async def find_by_reference(
        self,
        payment_reference: str,
        include_deleted: bool = False,
    ) -> Payment | None:
        """
        Find payment by reference number.
        
        Args:
            payment_reference: Payment reference
            include_deleted: Include soft-deleted records
            
        Returns:
            Payment if found
        """
        query = select(Payment).where(
            func.lower(Payment.payment_reference) == payment_reference.lower()
        )
        
        if not include_deleted:
            query = query.where(Payment.deleted_at.is_(None))
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_transaction_id(
        self,
        transaction_id: str,
    ) -> Payment | None:
        """
        Find payment by transaction ID.
        
        Args:
            transaction_id: Gateway transaction ID
            
        Returns:
            Payment if found
        """
        query = select(Payment).where(
            Payment.transaction_id == transaction_id,
            Payment.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        status: PaymentStatus | None = None,
        payment_type: PaymentType | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Payment]:
        """
        Find payments for a hostel with filters.
        
        Args:
            hostel_id: Hostel ID
            status: Filter by payment status
            payment_type: Filter by payment type
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of payments
        """
        query = select(Payment).where(
            Payment.hostel_id == hostel_id,
            Payment.deleted_at.is_(None),
        )
        
        if status:
            query = query.where(Payment.payment_status == status)
        
        if payment_type:
            query = query.where(Payment.payment_type == payment_type)
        
        if start_date:
            query = query.where(Payment.created_at >= datetime.combine(start_date, datetime.min.time()))
        
        if end_date:
            query = query.where(Payment.created_at <= datetime.combine(end_date, datetime.max.time()))
        
        query = query.order_by(Payment.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_student(
        self,
        student_id: UUID,
        status: PaymentStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Payment]:
        """
        Find payments for a student.
        
        Args:
            student_id: Student ID
            status: Filter by payment status
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of payments
        """
        query = select(Payment).where(
            Payment.student_id == student_id,
            Payment.deleted_at.is_(None),
        )
        
        if status:
            query = query.where(Payment.payment_status == status)
        
        query = query.order_by(Payment.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_overdue_payments(
        self,
        hostel_id: UUID | None = None,
        grace_period_days: int = 0,
    ) -> list[Payment]:
        """
        Find overdue payments.
        
        Args:
            hostel_id: Optional hostel ID filter
            grace_period_days: Grace period in days
            
        Returns:
            List of overdue payments
        """
        cutoff_date = date.today() - timedelta(days=grace_period_days)
        
        query = select(Payment).where(
            Payment.due_date < cutoff_date,
            Payment.payment_status.in_([PaymentStatus.PENDING, PaymentStatus.PROCESSING]),
            Payment.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(Payment.hostel_id == hostel_id)
        
        query = query.order_by(Payment.due_date.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_pending_payments(
        self,
        hostel_id: UUID | None = None,
        older_than_hours: int | None = None,
    ) -> list[Payment]:
        """
        Find pending payments.
        
        Args:
            hostel_id: Optional hostel ID filter
            older_than_hours: Find pending payments older than specified hours
            
        Returns:
            List of pending payments
        """
        query = select(Payment).where(
            Payment.payment_status == PaymentStatus.PENDING,
            Payment.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(Payment.hostel_id == hostel_id)
        
        if older_than_hours:
            cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
            query = query.where(Payment.created_at < cutoff_time)
        
        query = query.order_by(Payment.created_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_refunded_payments(
        self,
        hostel_id: UUID | None = None,
        partial_only: bool = False,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[Payment]:
        """
        Find refunded payments.
        
        Args:
            hostel_id: Optional hostel ID filter
            partial_only: Only partially refunded payments
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of refunded payments
        """
        query = select(Payment).where(
            Payment.is_refunded == True,
            Payment.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(Payment.hostel_id == hostel_id)
        
        if partial_only:
            query = query.where(Payment.refund_amount < Payment.amount)
        
        if start_date:
            query = query.where(Payment.created_at >= datetime.combine(start_date, datetime.min.time()))
        
        if end_date:
            query = query.where(Payment.created_at <= datetime.combine(end_date, datetime.max.time()))
        
        query = query.order_by(Payment.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Analytics Methods ====================

    async def calculate_revenue_statistics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        payment_type: PaymentType | None = None,
    ) -> dict[str, Any]:
        """
        Calculate revenue statistics for a period.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            payment_type: Optional payment type filter
            
        Returns:
            Revenue statistics
        """
        query = select(
            func.count(Payment.id).label("total_payments"),
            func.sum(Payment.amount).label("total_amount"),
            func.sum(Payment.refund_amount).label("total_refunds"),
            func.avg(Payment.amount).label("average_amount"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.paid_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.paid_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        )
        
        if payment_type:
            query = query.where(Payment.payment_type == payment_type)
        
        result = await self.session.execute(query)
        row = result.one()
        
        total_amount = row.total_amount or Decimal("0")
        total_refunds = row.total_refunds or Decimal("0")
        
        return {
            "total_payments": row.total_payments or 0,
            "total_amount": float(total_amount),
            "total_refunds": float(total_refunds),
            "net_revenue": float(total_amount - total_refunds),
            "average_amount": float(row.average_amount or Decimal("0")),
        }

    async def calculate_payment_success_rate(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        payment_method: PaymentMethod | None = None,
    ) -> dict[str, Any]:
        """
        Calculate payment success rate.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            payment_method: Optional payment method filter
            
        Returns:
            Success rate statistics
        """
        base_query = select(Payment).where(
            Payment.hostel_id == hostel_id,
            Payment.created_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.created_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        )
        
        if payment_method:
            base_query = base_query.where(Payment.payment_method == payment_method)
        
        # Total payments
        total_query = select(func.count(Payment.id)).select_from(base_query.subquery())
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0
        
        # Completed payments
        completed_query = select(func.count(Payment.id)).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.created_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.created_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        )
        
        if payment_method:
            completed_query = completed_query.where(Payment.payment_method == payment_method)
        
        completed_result = await self.session.execute(completed_query)
        completed = completed_result.scalar() or 0
        
        # Failed payments
        failed_query = select(func.count(Payment.id)).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.FAILED,
            Payment.created_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.created_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        )
        
        if payment_method:
            failed_query = failed_query.where(Payment.payment_method == payment_method)
        
        failed_result = await self.session.execute(failed_query)
        failed = failed_result.scalar() or 0
        
        success_rate = (completed / total * 100) if total > 0 else 0
        
        return {
            "total_payments": total,
            "completed_payments": completed,
            "failed_payments": failed,
            "pending_payments": total - completed - failed,
            "success_rate": round(success_rate, 2),
        }

    async def get_payment_method_distribution(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """
        Get payment method distribution.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Payment method distribution
        """
        query = select(
            Payment.payment_method,
            func.count(Payment.id).label("count"),
            func.sum(Payment.amount).label("total_amount"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.paid_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.paid_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        ).group_by(Payment.payment_method)
        
        result = await self.session.execute(query)
        
        return [
            {
                "payment_method": row.payment_method.value,
                "count": row.count,
                "total_amount": float(row.total_amount or Decimal("0")),
            }
            for row in result.all()
        ]

    async def get_revenue_trends(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        interval: str = "day",  # day, week, month
    ) -> list[dict[str, Any]]:
        """
        Get revenue trends over time.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            interval: Grouping interval (day, week, month)
            
        Returns:
            Revenue trend data
        """
        # Determine date truncation based on interval
        if interval == "day":
            date_trunc = func.date_trunc('day', Payment.paid_at)
        elif interval == "week":
            date_trunc = func.date_trunc('week', Payment.paid_at)
        else:  # month
            date_trunc = func.date_trunc('month', Payment.paid_at)
        
        query = select(
            date_trunc.label("period"),
            func.count(Payment.id).label("payment_count"),
            func.sum(Payment.amount).label("total_amount"),
            func.sum(Payment.refund_amount).label("total_refunds"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.paid_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.paid_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        ).group_by(date_trunc).order_by(date_trunc)
        
        result = await self.session.execute(query)
        
        return [
            {
                "period": row.period.isoformat() if row.period else None,
                "payment_count": row.payment_count,
                "total_amount": float(row.total_amount or Decimal("0")),
                "total_refunds": float(row.total_refunds or Decimal("0")),
                "net_revenue": float((row.total_amount or Decimal("0")) - (row.total_refunds or Decimal("0"))),
            }
            for row in result.all()
        ]

    # ==================== Reminder Management ====================

    async def get_payments_needing_reminders(
        self,
        hostel_id: UUID | None = None,
        days_before_due: int = 7,
        max_reminders: int = 3,
    ) -> list[Payment]:
        """
        Get payments that need reminders.
        
        Args:
            hostel_id: Optional hostel ID filter
            days_before_due: Days before due date to send reminder
            max_reminders: Maximum reminders already sent
            
        Returns:
            List of payments needing reminders
        """
        reminder_date = date.today() + timedelta(days=days_before_due)
        
        query = select(Payment).where(
            Payment.due_date <= reminder_date,
            Payment.payment_status.in_([PaymentStatus.PENDING, PaymentStatus.PROCESSING]),
            Payment.reminder_sent_count < max_reminders,
            Payment.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(Payment.hostel_id == hostel_id)
        
        query = query.order_by(Payment.due_date.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def increment_reminder_count(
        self,
        payment_id: UUID,
    ) -> Payment:
        """
        Increment reminder sent count.
        
        Args:
            payment_id: Payment ID
            
        Returns:
            Updated payment
        """
        payment = await self.get_by_id(payment_id)
        if not payment:
            raise ValueError(f"Payment not found: {payment_id}")
        
        update_data = {
            "reminder_sent_count": payment.reminder_sent_count + 1,
            "last_reminder_sent_at": datetime.utcnow(),
        }
        
        return await self.update(payment_id, update_data)

    # ==================== Bulk Operations ====================

    async def bulk_update_overdue_status(
        self,
        hostel_id: UUID | None = None,
    ) -> int:
        """
        Bulk update overdue status for pending payments.
        
        Args:
            hostel_id: Optional hostel ID filter
            
        Returns:
            Number of payments updated
        """
        from sqlalchemy import update as sql_update
        
        today = date.today()
        
        stmt = sql_update(Payment).where(
            Payment.due_date < today,
            Payment.payment_status.in_([PaymentStatus.PENDING, PaymentStatus.PROCESSING]),
            Payment.is_overdue == False,
            Payment.deleted_at.is_(None),
        ).values(is_overdue=True)
        
        if hostel_id:
            stmt = stmt.where(Payment.hostel_id == hostel_id)
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        return result.rowcount

    # ==================== Helper Methods ====================

    async def _generate_payment_reference(self, hostel_id: UUID) -> str:
        """Generate unique payment reference."""
        # Get count of payments for today
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        query = select(func.count(Payment.id)).where(
            Payment.hostel_id == hostel_id,
            Payment.created_at >= today_start,
        )
        
        result = await self.session.execute(query)
        count = result.scalar() or 0
        
        # Format: PAY-YYYYMMDD-NNNN
        return f"PAY-{date.today().strftime('%Y%m%d')}-{count + 1:04d}"

    async def _generate_receipt_number(self, payment_id: UUID) -> str:
        """Generate unique receipt number."""
        payment = await self.get_by_id(payment_id)
        if not payment:
            raise ValueError(f"Payment not found: {payment_id}")
        
        # Format: RCP-YYYYMMDD-NNNN
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        query = select(func.count(Payment.id)).where(
            Payment.hostel_id == payment.hostel_id,
            Payment.receipt_generated_at >= today_start,
            Payment.receipt_number.isnot(None),
        )
        
        result = await self.session.execute(query)
        count = result.scalar() or 0
        
        return f"RCP-{date.today().strftime('%Y%m%d')}-{count + 1:04d}"