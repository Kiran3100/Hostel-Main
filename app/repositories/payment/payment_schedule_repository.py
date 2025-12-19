# --- File: payment_schedule_repository.py ---
"""
Payment Schedule Repository.

Manages recurring payment schedules for students.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment.payment_schedule import (
    PaymentSchedule,
    ScheduleStatus,
)
from app.repositories.base.base_repository import BaseRepository
from app.schemas.common.enums import FeeType


class PaymentScheduleRepository(BaseRepository[PaymentSchedule]):
    """Repository for payment schedule operations."""

    def __init__(self, session: AsyncSession):
        """Initialize payment schedule repository."""
        super().__init__(PaymentSchedule, session)

    # ==================== Core Schedule Operations ====================

    async def create_schedule(
        self,
        student_id: UUID,
        hostel_id: UUID,
        fee_type: FeeType,
        amount: Decimal,
        start_date: date,
        frequency_days: int,
        end_date: date | None = None,
        day_of_month: int | None = None,
        auto_generate_invoice: bool = True,
        auto_send_reminders: bool = True,
        days_before_due_reminder: int = 7,
        metadata: dict | None = None,
    ) -> PaymentSchedule:
        """
        Create a new payment schedule.
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            fee_type: Type of fee
            amount: Amount per period
            start_date: Schedule start date
            frequency_days: Days between payments
            end_date: Optional end date
            day_of_month: Specific day of month for payment
            auto_generate_invoice: Auto-generate invoices
            auto_send_reminders: Auto-send reminders
            days_before_due_reminder: Days before due to send reminder
            metadata: Additional metadata
            
        Returns:
            Created schedule
        """
        schedule_reference = await self._generate_schedule_reference()
        
        schedule_data = {
            "student_id": student_id,
            "hostel_id": hostel_id,
            "schedule_reference": schedule_reference,
            "fee_type": fee_type,
            "amount": amount,
            "start_date": start_date,
            "end_date": end_date,
            "next_due_date": start_date,
            "frequency_days": frequency_days,
            "day_of_month": day_of_month,
            "auto_generate_invoice": auto_generate_invoice,
            "auto_send_reminders": auto_send_reminders,
            "days_before_due_reminder": days_before_due_reminder,
            "schedule_status": ScheduleStatus.ACTIVE,
            "is_active": True,
            "metadata": metadata or {},
        }
        
        return await self.create(schedule_data)

    async def update_next_due_date(
        self,
        schedule_id: UUID,
        next_due_date: date,
    ) -> PaymentSchedule:
        """
        Update next due date for a schedule.
        
        Args:
            schedule_id: Schedule ID
            next_due_date: Next due date
            
        Returns:
            Updated schedule
        """
        update_data = {
            "next_due_date": next_due_date,
            "last_generated_date": date.today(),
        }
        
        return await self.update(schedule_id, update_data)

    async def increment_payment_generated(
        self,
        schedule_id: UUID,
        payment_amount: Decimal,
    ) -> PaymentSchedule:
        """
        Increment payment generated count.
        
        Args:
            schedule_id: Schedule ID
            payment_amount: Amount of payment generated
            
        Returns:
            Updated schedule
        """
        schedule = await self.get_by_id(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule not found: {schedule_id}")
        
        update_data = {
            "total_payments_generated": schedule.total_payments_generated + 1,
            "last_generated_date": date.today(),
        }
        
        return await self.update(schedule_id, update_data)

    async def increment_payment_completed(
        self,
        schedule_id: UUID,
        payment_amount: Decimal,
    ) -> PaymentSchedule:
        """
        Increment payment completed count.
        
        Args:
            schedule_id: Schedule ID
            payment_amount: Amount of payment completed
            
        Returns:
            Updated schedule
        """
        schedule = await self.get_by_id(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule not found: {schedule_id}")
        
        update_data = {
            "total_payments_completed": schedule.total_payments_completed + 1,
            "total_amount_collected": schedule.total_amount_collected + payment_amount,
        }
        
        return await self.update(schedule_id, update_data)

    async def suspend_schedule(
        self,
        schedule_id: UUID,
        suspension_reason: str,
        suspension_start_date: date | None = None,
        suspension_end_date: date | None = None,
        skip_during_suspension: bool = True,
    ) -> PaymentSchedule:
        """
        Suspend a payment schedule.
        
        Args:
            schedule_id: Schedule ID
            suspension_reason: Reason for suspension
            suspension_start_date: Suspension start date
            suspension_end_date: Suspension end date
            skip_during_suspension: Skip payment generation
            
        Returns:
            Updated schedule
        """
        update_data = {
            "schedule_status": ScheduleStatus.SUSPENDED,
            "is_active": False,
            "suspended_at": datetime.utcnow(),
            "suspension_reason": suspension_reason,
            "suspension_start_date": suspension_start_date or date.today(),
            "suspension_end_date": suspension_end_date,
            "skip_during_suspension": skip_during_suspension,
        }
        
        return await self.update(schedule_id, update_data)

    async def resume_schedule(
        self,
        schedule_id: UUID,
    ) -> PaymentSchedule:
        """
        Resume a suspended schedule.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            Updated schedule
        """
        update_data = {
            "schedule_status": ScheduleStatus.ACTIVE,
            "is_active": True,
            "suspended_at": None,
            "suspension_reason": None,
            "suspension_start_date": None,
            "suspension_end_date": None,
        }
        
        return await self.update(schedule_id, update_data)

    async def pause_schedule(
        self,
        schedule_id: UUID,
    ) -> PaymentSchedule:
        """
        Pause a schedule temporarily.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            Updated schedule
        """
        update_data = {
            "schedule_status": ScheduleStatus.PAUSED,
            "is_active": False,
        }
        
        return await self.update(schedule_id, update_data)

    async def complete_schedule(
        self,
        schedule_id: UUID,
        completion_reason: str | None = None,
    ) -> PaymentSchedule:
        """
        Mark schedule as completed.
        
        Args:
            schedule_id: Schedule ID
            completion_reason: Reason for completion
            
        Returns:
            Updated schedule
        """
        update_data = {
            "schedule_status": ScheduleStatus.COMPLETED,
            "is_active": False,
            "completed_at": datetime.utcnow(),
            "completion_reason": completion_reason,
        }
        
        return await self.update(schedule_id, update_data)

    async def cancel_schedule(
        self,
        schedule_id: UUID,
    ) -> PaymentSchedule:
        """
        Cancel a schedule.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            Updated schedule
        """
        update_data = {
            "schedule_status": ScheduleStatus.CANCELLED,
            "is_active": False,
        }
        
        return await self.update(schedule_id, update_data)

    # ==================== Query Methods ====================

    async def find_by_reference(
        self,
        schedule_reference: str,
    ) -> PaymentSchedule | None:
        """
        Find schedule by reference.
        
        Args:
            schedule_reference: Schedule reference
            
        Returns:
            Schedule if found
        """
        query = select(PaymentSchedule).where(
            func.lower(PaymentSchedule.schedule_reference) == schedule_reference.lower(),
            PaymentSchedule.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_student(
        self,
        student_id: UUID,
        status: ScheduleStatus | None = None,
        active_only: bool = False,
    ) -> list[PaymentSchedule]:
        """
        Find schedules for a student.
        
        Args:
            student_id: Student ID
            status: Optional status filter
            active_only: Only active schedules
            
        Returns:
            List of schedules
        """
        query = select(PaymentSchedule).where(
            PaymentSchedule.student_id == student_id,
            PaymentSchedule.deleted_at.is_(None),
        )
        
        if status:
            query = query.where(PaymentSchedule.schedule_status == status)
        
        if active_only:
            query = query.where(PaymentSchedule.is_active == True)
        
        query = query.order_by(PaymentSchedule.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        status: ScheduleStatus | None = None,
        fee_type: FeeType | None = None,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaymentSchedule]:
        """
        Find schedules for a hostel.
        
        Args:
            hostel_id: Hostel ID
            status: Optional status filter
            fee_type: Optional fee type filter
            active_only: Only active schedules
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of schedules
        """
        query = select(PaymentSchedule).where(
            PaymentSchedule.hostel_id == hostel_id,
            PaymentSchedule.deleted_at.is_(None),
        )
        
        if status:
            query = query.where(PaymentSchedule.schedule_status == status)
        
        if fee_type:
            query = query.where(PaymentSchedule.fee_type == fee_type)
        
        if active_only:
            query = query.where(PaymentSchedule.is_active == True)
        
        query = query.order_by(PaymentSchedule.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_due_schedules(
        self,
        hostel_id: UUID | None = None,
        up_to_date: date | None = None,
    ) -> list[PaymentSchedule]:
        """
        Find schedules with payments due.
        
        Args:
            hostel_id: Optional hostel ID filter
            up_to_date: Find schedules due up to this date
            
        Returns:
            List of due schedules
        """
        target_date = up_to_date or date.today()
        
        query = select(PaymentSchedule).where(
            PaymentSchedule.next_due_date <= target_date,
            PaymentSchedule.is_active == True,
            PaymentSchedule.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(PaymentSchedule.hostel_id == hostel_id)
        
        query = query.order_by(PaymentSchedule.next_due_date.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_overdue_schedules(
        self,
        hostel_id: UUID | None = None,
        grace_period_days: int = 0,
    ) -> list[PaymentSchedule]:
        """
        Find overdue payment schedules.
        
        Args:
            hostel_id: Optional hostel ID filter
            grace_period_days: Grace period in days
            
        Returns:
            List of overdue schedules
        """
        cutoff_date = date.today() - timedelta(days=grace_period_days)
        
        query = select(PaymentSchedule).where(
            PaymentSchedule.next_due_date < cutoff_date,
            PaymentSchedule.is_active == True,
            PaymentSchedule.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(PaymentSchedule.hostel_id == hostel_id)
        
        query = query.order_by(PaymentSchedule.next_due_date.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_expiring_schedules(
        self,
        hostel_id: UUID | None = None,
        days_until_expiry: int = 30,
    ) -> list[PaymentSchedule]:
        """
        Find schedules expiring soon.
        
        Args:
            hostel_id: Optional hostel ID filter
            days_until_expiry: Days until expiry threshold
            
        Returns:
            List of expiring schedules
        """
        cutoff_date = date.today() + timedelta(days=days_until_expiry)
        
        query = select(PaymentSchedule).where(
            PaymentSchedule.end_date.isnot(None),
            PaymentSchedule.end_date <= cutoff_date,
            PaymentSchedule.is_active == True,
            PaymentSchedule.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(PaymentSchedule.hostel_id == hostel_id)
        
        query = query.order_by(PaymentSchedule.end_date.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_suspended_schedules(
        self,
        hostel_id: UUID | None = None,
        ready_to_resume: bool = False,
    ) -> list[PaymentSchedule]:
        """
        Find suspended schedules.
        
        Args:
            hostel_id: Optional hostel ID filter
            ready_to_resume: Only schedules ready to resume
            
        Returns:
            List of suspended schedules
        """
        query = select(PaymentSchedule).where(
            PaymentSchedule.schedule_status == ScheduleStatus.SUSPENDED,
            PaymentSchedule.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(PaymentSchedule.hostel_id == hostel_id)
        
        if ready_to_resume:
            today = date.today()
            query = query.where(
                or_(
                    PaymentSchedule.suspension_end_date.is_(None),
                    PaymentSchedule.suspension_end_date <= today,
                )
            )
        
        query = query.order_by(PaymentSchedule.suspended_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Analytics Methods ====================

    async def calculate_schedule_statistics(
        self,
        hostel_id: UUID,
    ) -> dict[str, Any]:
        """
        Calculate schedule statistics for a hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Schedule statistics
        """
        # Total schedules
        total_query = select(func.count(PaymentSchedule.id)).where(
            PaymentSchedule.hostel_id == hostel_id,
            PaymentSchedule.deleted_at.is_(None),
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0
        
        # Active schedules
        active_query = select(func.count(PaymentSchedule.id)).where(
            PaymentSchedule.hostel_id == hostel_id,
            PaymentSchedule.is_active == True,
            PaymentSchedule.deleted_at.is_(None),
        )
        active_result = await self.session.execute(active_query)
        active = active_result.scalar() or 0
        
        # Status breakdown
        status_query = select(
            PaymentSchedule.schedule_status,
            func.count(PaymentSchedule.id).label("count"),
        ).where(
            PaymentSchedule.hostel_id == hostel_id,
            PaymentSchedule.deleted_at.is_(None),
        ).group_by(PaymentSchedule.schedule_status)
        
        status_result = await self.session.execute(status_query)
        status_breakdown = {row.schedule_status.value: row.count for row in status_result.all()}
        
        # Fee type distribution
        fee_type_query = select(
            PaymentSchedule.fee_type,
            func.count(PaymentSchedule.id).label("count"),
            func.sum(PaymentSchedule.amount).label("total_amount"),
        ).where(
            PaymentSchedule.hostel_id == hostel_id,
            PaymentSchedule.is_active == True,
            PaymentSchedule.deleted_at.is_(None),
        ).group_by(PaymentSchedule.fee_type)
        
        fee_type_result = await self.session.execute(fee_type_query)
        fee_type_distribution = [
            {
                "fee_type": row.fee_type.value,
                "count": row.count,
                "total_amount": float(row.total_amount or Decimal("0")),
            }
            for row in fee_type_result.all()
        ]
        
        # Collection statistics
        collection_query = select(
            func.sum(PaymentSchedule.total_payments_generated).label("total_generated"),
            func.sum(PaymentSchedule.total_payments_completed).label("total_completed"),
            func.sum(PaymentSchedule.total_amount_collected).label("total_collected"),
        ).where(
            PaymentSchedule.hostel_id == hostel_id,
            PaymentSchedule.deleted_at.is_(None),
        )
        
        collection_result = await self.session.execute(collection_query)
        collection_row = collection_result.one()
        
        return {
            "total_schedules": total,
            "active_schedules": active,
            "status_breakdown": status_breakdown,
            "fee_type_distribution": fee_type_distribution,
            "collection_statistics": {
                "total_payments_generated": collection_row.total_generated or 0,
                "total_payments_completed": collection_row.total_completed or 0,
                "total_amount_collected": float(collection_row.total_collected or Decimal("0")),
            },
        }

    async def calculate_collection_rate(
        self,
        hostel_id: UUID,
        fee_type: FeeType | None = None,
    ) -> dict[str, Any]:
        """
        Calculate payment collection rate.
        
        Args:
            hostel_id: Hostel ID
            fee_type: Optional fee type filter
            
        Returns:
            Collection rate statistics
        """
        query = select(
            func.sum(PaymentSchedule.total_payments_generated).label("generated"),
            func.sum(PaymentSchedule.total_payments_completed).label("completed"),
            func.avg(
                func.cast(PaymentSchedule.total_payments_completed, Decimal) /
                func.nullif(func.cast(PaymentSchedule.total_payments_generated, Decimal), 0) * 100
            ).label("avg_collection_rate"),
        ).where(
            PaymentSchedule.hostel_id == hostel_id,
            PaymentSchedule.total_payments_generated > 0,
            PaymentSchedule.deleted_at.is_(None),
        )
        
        if fee_type:
            query = query.where(PaymentSchedule.fee_type == fee_type)
        
        result = await self.session.execute(query)
        row = result.one()
        
        overall_rate = (
            (row.completed / row.generated * 100)
            if row.generated and row.generated > 0 else 0
        )
        
        return {
            "total_generated": row.generated or 0,
            "total_completed": row.completed or 0,
            "overall_collection_rate": round(overall_rate, 2),
            "average_collection_rate": round(row.avg_collection_rate or 0, 2),
        }

    async def get_revenue_projection(
        self,
        hostel_id: UUID,
        months_ahead: int = 12,
    ) -> list[dict[str, Any]]:
        """
        Project future revenue from active schedules.
        
        Args:
            hostel_id: Hostel ID
            months_ahead: Months to project
            
        Returns:
            Monthly revenue projections
        """
        # Get all active schedules
        schedules = await self.find_by_hostel(
            hostel_id=hostel_id,
            active_only=True,
            limit=10000,
        )
        
        # Calculate projections for each month
        projections = []
        current_date = date.today()
        
        for month_offset in range(months_ahead):
            target_date = current_date + timedelta(days=30 * month_offset)
            month_revenue = Decimal("0")
            payment_count = 0
            
            for schedule in schedules:
                # Check if schedule is active in this month
                if schedule.end_date and schedule.end_date < target_date:
                    continue
                
                if schedule.start_date > target_date:
                    continue
                
                # Calculate number of payments in this month
                # This is a simplified calculation
                payments_per_month = 30 / schedule.frequency_days
                month_revenue += schedule.amount * Decimal(str(payments_per_month))
                payment_count += int(payments_per_month)
            
            projections.append({
                "month": target_date.strftime("%Y-%m"),
                "projected_revenue": float(month_revenue),
                "projected_payment_count": payment_count,
            })
        
        return projections

    # ==================== Helper Methods ====================

    async def _generate_schedule_reference(self) -> str:
        """Generate unique schedule reference."""
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        query = select(func.count(PaymentSchedule.id)).where(
            PaymentSchedule.created_at >= today_start,
        )
        
        result = await self.session.execute(query)
        count = result.scalar() or 0
        
        # Format: SCH-YYYYMMDD-NNNN
        return f"SCH-{date.today().strftime('%Y%m%d')}-{count + 1:04d}"