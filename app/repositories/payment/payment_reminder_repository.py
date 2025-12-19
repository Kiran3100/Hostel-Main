# --- File: payment_reminder_repository.py ---
"""
Payment Reminder Repository.

Manages payment reminder configuration and delivery tracking.
"""

from datetime import datetime, timedelta, date
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment.payment_reminder import (
    PaymentReminder,
    ReminderStatus,
    ReminderType,
)
from app.repositories.base.base_repository import BaseRepository


class PaymentReminderRepository(BaseRepository[PaymentReminder]):
    """Repository for payment reminder operations."""

    def __init__(self, session: AsyncSession):
        """Initialize payment reminder repository."""
        super().__init__(PaymentReminder, session)

    # ==================== Core Reminder Operations ====================

    async def create_reminder(
        self,
        payment_id: UUID,
        student_id: UUID,
        hostel_id: UUID,
        reminder_type: ReminderType,
        reminder_number: int,
        recipient_name: str,
        recipient_email: str | None = None,
        recipient_phone: str | None = None,
        scheduled_for: datetime | None = None,
        template_id: str | None = None,
        template_variables: dict | None = None,
        metadata: dict | None = None,
    ) -> PaymentReminder:
        """
        Create a new payment reminder.
        
        Args:
            payment_id: Payment ID
            student_id: Student ID
            hostel_id: Hostel ID
            reminder_type: Type of reminder
            reminder_number: Sequence number
            recipient_name: Recipient name
            recipient_email: Recipient email
            recipient_phone: Recipient phone
            scheduled_for: When to send reminder
            template_id: Template ID to use
            template_variables: Variables for template
            metadata: Additional metadata
            
        Returns:
            Created reminder
        """
        reminder_reference = await self._generate_reminder_reference()
        
        reminder_data = {
            "payment_id": payment_id,
            "student_id": student_id,
            "hostel_id": hostel_id,
            "reminder_reference": reminder_reference,
            "reminder_type": reminder_type,
            "reminder_number": reminder_number,
            "recipient_name": recipient_name,
            "recipient_email": recipient_email,
            "recipient_phone": recipient_phone,
            "reminder_status": ReminderStatus.PENDING,
            "scheduled_for": scheduled_for or datetime.utcnow(),
            "template_id": template_id,
            "template_variables": template_variables or {},
            "metadata": metadata or {},
        }
        
        return await self.create(reminder_data)

    async def mark_reminder_sent(
        self,
        reminder_id: UUID,
        sent_via_email: bool = False,
        sent_via_sms: bool = False,
        sent_via_push: bool = False,
        email_message_id: str | None = None,
        sms_message_id: str | None = None,
        push_notification_id: str | None = None,
    ) -> PaymentReminder:
        """
        Mark reminder as sent.
        
        Args:
            reminder_id: Reminder ID
            sent_via_email: Sent via email
            sent_via_sms: Sent via SMS
            sent_via_push: Sent via push notification
            email_message_id: Email message ID
            sms_message_id: SMS message ID
            push_notification_id: Push notification ID
            
        Returns:
            Updated reminder
        """
        update_data = {
            "reminder_status": ReminderStatus.SENT,
            "sent_at": datetime.utcnow(),
            "sent_via_email": sent_via_email,
            "sent_via_sms": sent_via_sms,
            "sent_via_push": sent_via_push,
            "email_message_id": email_message_id,
            "sms_message_id": sms_message_id,
            "push_notification_id": push_notification_id,
        }
        
        return await self.update(reminder_id, update_data)

    async def mark_reminder_delivered(
        self,
        reminder_id: UUID,
    ) -> PaymentReminder:
        """
        Mark reminder as delivered.
        
        Args:
            reminder_id: Reminder ID
            
        Returns:
            Updated reminder
        """
        update_data = {
            "reminder_status": ReminderStatus.DELIVERED,
        }
        
        return await self.update(reminder_id, update_data)

    async def mark_reminder_failed(
        self,
        reminder_id: UUID,
        error_message: str,
    ) -> PaymentReminder:
        """
        Mark reminder as failed.
        
        Args:
            reminder_id: Reminder ID
            error_message: Error message
            
        Returns:
            Updated reminder
        """
        update_data = {
            "reminder_status": ReminderStatus.FAILED,
            "error_message": error_message,
        }
        
        return await self.update(reminder_id, update_data)

    async def track_email_opened(
        self,
        reminder_id: UUID,
    ) -> PaymentReminder:
        """
        Track email opened event.
        
        Args:
            reminder_id: Reminder ID
            
        Returns:
            Updated reminder
        """
        update_data = {
            "email_opened": True,
            "opened_at": datetime.utcnow(),
        }
        
        return await self.update(reminder_id, update_data)

    async def track_email_clicked(
        self,
        reminder_id: UUID,
    ) -> PaymentReminder:
        """
        Track email link clicked event.
        
        Args:
            reminder_id: Reminder ID
            
        Returns:
            Updated reminder
        """
        update_data = {
            "email_clicked": True,
            "clicked_at": datetime.utcnow(),
        }
        
        return await self.update(reminder_id, update_data)

    async def track_sms_delivered(
        self,
        reminder_id: UUID,
    ) -> PaymentReminder:
        """
        Track SMS delivered event.
        
        Args:
            reminder_id: Reminder ID
            
        Returns:
            Updated reminder
        """
        update_data = {
            "sms_delivered": True,
            "sms_delivered_at": datetime.utcnow(),
        }
        
        return await self.update(reminder_id, update_data)

    async def track_push_clicked(
        self,
        reminder_id: UUID,
    ) -> PaymentReminder:
        """
        Track push notification clicked event.
        
        Args:
            reminder_id: Reminder ID
            
        Returns:
            Updated reminder
        """
        update_data = {
            "push_clicked": True,
        }
        
        return await self.update(reminder_id, update_data)

    async def increment_retry_count(
        self,
        reminder_id: UUID,
    ) -> PaymentReminder:
        """
        Increment retry count.
        
        Args:
            reminder_id: Reminder ID
            
        Returns:
            Updated reminder
        """
        reminder = await self.get_by_id(reminder_id)
        if not reminder:
            raise ValueError(f"Reminder not found: {reminder_id}")
        
        update_data = {
            "retry_count": reminder.retry_count + 1,
            "last_retry_at": datetime.utcnow(),
        }
        
        return await self.update(reminder_id, update_data)

    # ==================== Query Methods ====================

    async def find_by_reference(
        self,
        reminder_reference: str,
    ) -> PaymentReminder | None:
        """
        Find reminder by reference.
        
        Args:
            reminder_reference: Reminder reference
            
        Returns:
            Reminder if found
        """
        query = select(PaymentReminder).where(
            func.lower(PaymentReminder.reminder_reference) == reminder_reference.lower(),
            PaymentReminder.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_payment(
        self,
        payment_id: UUID,
        reminder_type: ReminderType | None = None,
    ) -> list[PaymentReminder]:
        """
        Find reminders for a payment.
        
        Args:
            payment_id: Payment ID
            reminder_type: Optional reminder type filter
            
        Returns:
            List of reminders
        """
        query = select(PaymentReminder).where(
            PaymentReminder.payment_id == payment_id,
            PaymentReminder.deleted_at.is_(None),
        )
        
        if reminder_type:
            query = query.where(PaymentReminder.reminder_type == reminder_type)
        
        query = query.order_by(PaymentReminder.sent_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_student(
        self,
        student_id: UUID,
        status: ReminderStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaymentReminder]:
        """
        Find reminders for a student.
        
        Args:
            student_id: Student ID
            status: Optional status filter
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of reminders
        """
        query = select(PaymentReminder).where(
            PaymentReminder.student_id == student_id,
            PaymentReminder.deleted_at.is_(None),
        )
        
        if status:
            query = query.where(PaymentReminder.reminder_status == status)
        
        query = query.order_by(PaymentReminder.sent_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        status: ReminderStatus | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaymentReminder]:
        """
        Find reminders for a hostel.
        
        Args:
            hostel_id: Hostel ID
            status: Optional status filter
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of reminders
        """
        query = select(PaymentReminder).where(
            PaymentReminder.hostel_id == hostel_id,
            PaymentReminder.deleted_at.is_(None),
        )
        
        if status:
            query = query.where(PaymentReminder.reminder_status == status)
        
        if start_date:
            query = query.where(PaymentReminder.sent_at >= start_date)
        
        if end_date:
            query = query.where(PaymentReminder.sent_at <= end_date)
        
        query = query.order_by(PaymentReminder.sent_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_pending_reminders(
        self,
        hostel_id: UUID | None = None,
    ) -> list[PaymentReminder]:
        """
        Find pending reminders ready to be sent.
        
        Args:
            hostel_id: Optional hostel ID filter
            
        Returns:
            List of pending reminders
        """
        now = datetime.utcnow()
        
        query = select(PaymentReminder).where(
            PaymentReminder.reminder_status == ReminderStatus.PENDING,
            PaymentReminder.scheduled_for <= now,
            PaymentReminder.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(PaymentReminder.hostel_id == hostel_id)
        
        query = query.order_by(PaymentReminder.scheduled_for.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_failed_reminders(
        self,
        hostel_id: UUID | None = None,
        max_retries: int = 3,
    ) -> list[PaymentReminder]:
        """
        Find failed reminders that can be retried.
        
        Args:
            hostel_id: Optional hostel ID filter
            max_retries: Maximum retry attempts
            
        Returns:
            List of failed reminders
        """
        query = select(PaymentReminder).where(
            PaymentReminder.reminder_status == ReminderStatus.FAILED,
            PaymentReminder.retry_count < max_retries,
            PaymentReminder.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(PaymentReminder.hostel_id == hostel_id)
        
        query = query.order_by(PaymentReminder.last_retry_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_email_message_id(
        self,
        email_message_id: str,
    ) -> PaymentReminder | None:
        """
        Find reminder by email message ID.
        
        Args:
            email_message_id: Email message ID
            
        Returns:
            Reminder if found
        """
        query = select(PaymentReminder).where(
            PaymentReminder.email_message_id == email_message_id,
            PaymentReminder.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_sms_message_id(
        self,
        sms_message_id: str,
    ) -> PaymentReminder | None:
        """
        Find reminder by SMS message ID.
        
        Args:
            sms_message_id: SMS message ID
            
        Returns:
            Reminder if found
        """
        query = select(PaymentReminder).where(
            PaymentReminder.sms_message_id == sms_message_id,
            PaymentReminder.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    # ==================== Analytics Methods ====================

    async def calculate_reminder_statistics(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Calculate reminder statistics.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Reminder statistics
        """
        # Total reminders
        total_query = select(func.count(PaymentReminder.id)).where(
            PaymentReminder.hostel_id == hostel_id,
            PaymentReminder.sent_at >= start_date,
            PaymentReminder.sent_at <= end_date,
            PaymentReminder.deleted_at.is_(None),
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0
        
        # Status breakdown
        status_query = select(
            PaymentReminder.reminder_status,
            func.count(PaymentReminder.id).label("count"),
        ).where(
            PaymentReminder.hostel_id == hostel_id,
            PaymentReminder.sent_at >= start_date,
            PaymentReminder.sent_at <= end_date,
            PaymentReminder.deleted_at.is_(None),
        ).group_by(PaymentReminder.reminder_status)
        
        status_result = await self.session.execute(status_query)
        status_breakdown = {row.reminder_status.value: row.count for row in status_result.all()}
        
        # Email engagement
        email_query = select(
            func.count(PaymentReminder.id).filter(
                PaymentReminder.sent_via_email == True
            ).label("sent_via_email"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.email_opened == True
            ).label("email_opened"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.email_clicked == True
            ).label("email_clicked"),
        ).where(
            PaymentReminder.hostel_id == hostel_id,
            PaymentReminder.sent_at >= start_date,
            PaymentReminder.sent_at <= end_date,
            PaymentReminder.deleted_at.is_(None),
        )
        
        email_result = await self.session.execute(email_query)
        email_row = email_result.one()
        
        email_open_rate = (
            (email_row.email_opened / email_row.sent_via_email * 100)
            if email_row.sent_via_email > 0 else 0
        )
        email_click_rate = (
            (email_row.email_clicked / email_row.sent_via_email * 100)
            if email_row.sent_via_email > 0 else 0
        )
        
        # SMS delivery
        sms_query = select(
            func.count(PaymentReminder.id).filter(
                PaymentReminder.sent_via_sms == True
            ).label("sent_via_sms"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.sms_delivered == True
            ).label("sms_delivered"),
        ).where(
            PaymentReminder.hostel_id == hostel_id,
            PaymentReminder.sent_at >= start_date,
            PaymentReminder.sent_at <= end_date,
            PaymentReminder.deleted_at.is_(None),
        )
        
        sms_result = await self.session.execute(sms_query)
        sms_row = sms_result.one()
        
        sms_delivery_rate = (
            (sms_row.sms_delivered / sms_row.sent_via_sms * 100)
            if sms_row.sent_via_sms > 0 else 0
        )
        
        return {
            "total_reminders": total,
            "status_breakdown": status_breakdown,
            "email_statistics": {
                "sent": email_row.sent_via_email,
                "opened": email_row.email_opened,
                "clicked": email_row.email_clicked,
                "open_rate": round(email_open_rate, 2),
                "click_rate": round(email_click_rate, 2),
            },
            "sms_statistics": {
                "sent": sms_row.sent_via_sms,
                "delivered": sms_row.sms_delivered,
                "delivery_rate": round(sms_delivery_rate, 2),
            },
        }

    async def get_reminder_effectiveness(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Calculate reminder effectiveness by type.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Effectiveness metrics by reminder type
        """
        query = select(
            PaymentReminder.reminder_type,
            func.count(PaymentReminder.id).label("total"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.email_opened == True
            ).label("email_opened"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.email_clicked == True
            ).label("email_clicked"),
            func.avg(
                func.extract('epoch', PaymentReminder.opened_at - PaymentReminder.sent_at) / 3600
            ).label("avg_time_to_open_hours"),
        ).where(
            PaymentReminder.hostel_id == hostel_id,
            PaymentReminder.sent_at >= start_date,
            PaymentReminder.sent_at <= end_date,
            PaymentReminder.deleted_at.is_(None),
        ).group_by(PaymentReminder.reminder_type)
        
        result = await self.session.execute(query)
        
        effectiveness = []
        for row in result.all():
            open_rate = (row.email_opened / row.total * 100) if row.total > 0 else 0
            click_rate = (row.email_clicked / row.total * 100) if row.total > 0 else 0
            
            effectiveness.append({
                "reminder_type": row.reminder_type.value,
                "total_sent": row.total,
                "email_opened": row.email_opened,
                "email_clicked": row.email_clicked,
                "open_rate": round(open_rate, 2),
                "click_rate": round(click_rate, 2),
                "avg_time_to_open_hours": round(row.avg_time_to_open_hours or 0, 2),
            })
        
        return {"effectiveness_by_type": effectiveness}

    async def get_channel_performance(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Compare performance across delivery channels.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Channel performance comparison
        """
        query = select(
            func.count(PaymentReminder.id).filter(
                PaymentReminder.sent_via_email == True
            ).label("email_sent"),
            func.count(PaymentReminder.id).filter(
                and_(
                    PaymentReminder.sent_via_email == True,
                    PaymentReminder.reminder_status == ReminderStatus.DELIVERED
                )
            ).label("email_delivered"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.sent_via_sms == True
            ).label("sms_sent"),
            func.count(PaymentReminder.id).filter(
                and_(
                    PaymentReminder.sent_via_sms == True,
                    PaymentReminder.sms_delivered == True
                )
            ).label("sms_delivered"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.sent_via_push == True
            ).label("push_sent"),
            func.count(PaymentReminder.id).filter(
                and_(
                    PaymentReminder.sent_via_push == True,
                    PaymentReminder.push_clicked == True
                )
            ).label("push_clicked"),
        ).where(
            PaymentReminder.hostel_id == hostel_id,
            PaymentReminder.sent_at >= start_date,
            PaymentReminder.sent_at <= end_date,
            PaymentReminder.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        row = result.one()
        
        email_delivery_rate = (
            (row.email_delivered / row.email_sent * 100)
            if row.email_sent > 0 else 0
        )
        sms_delivery_rate = (
            (row.sms_delivered / row.sms_sent * 100)
            if row.sms_sent > 0 else 0
        )
        push_click_rate = (
            (row.push_clicked / row.push_sent * 100)
            if row.push_sent > 0 else 0
        )
        
        return {
            "email": {
                "sent": row.email_sent,
                "delivered": row.email_delivered,
                "delivery_rate": round(email_delivery_rate, 2),
            },
            "sms": {
                "sent": row.sms_sent,
                "delivered": row.sms_delivered,
                "delivery_rate": round(sms_delivery_rate, 2),
            },
            "push": {
                "sent": row.push_sent,
                "clicked": row.push_clicked,
                "click_rate": round(push_click_rate, 2),
            },
        }

    async def get_engagement_trends(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
        interval: str = "day",  # day, week, month
    ) -> list[dict[str, Any]]:
        """
        Get engagement trends over time.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            interval: Grouping interval
            
        Returns:
            Engagement trend data
        """
        # Determine date truncation
        if interval == "day":
            date_trunc = func.date_trunc('day', PaymentReminder.sent_at)
        elif interval == "week":
            date_trunc = func.date_trunc('week', PaymentReminder.sent_at)
        else:  # month
            date_trunc = func.date_trunc('month', PaymentReminder.sent_at)
        
        query = select(
            date_trunc.label("period"),
            func.count(PaymentReminder.id).label("total_sent"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.email_opened == True
            ).label("email_opened"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.email_clicked == True
            ).label("email_clicked"),
        ).where(
            PaymentReminder.hostel_id == hostel_id,
            PaymentReminder.sent_at >= start_date,
            PaymentReminder.sent_at <= end_date,
            PaymentReminder.deleted_at.is_(None),
        ).group_by(date_trunc).order_by(date_trunc)
        
        result = await self.session.execute(query)
        
        trends = []
        for row in result.all():
            open_rate = (row.email_opened / row.total_sent * 100) if row.total_sent > 0 else 0
            click_rate = (row.email_clicked / row.total_sent * 100) if row.total_sent > 0 else 0
            
            trends.append({
                "period": row.period.isoformat() if row.period else None,
                "total_sent": row.total_sent,
                "email_opened": row.email_opened,
                "email_clicked": row.email_clicked,
                "open_rate": round(open_rate, 2),
                "click_rate": round(click_rate, 2),
            })
        
        return trends

    # ==================== Helper Methods ====================

    async def _generate_reminder_reference(self) -> str:
        """Generate unique reminder reference."""
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        query = select(func.count(PaymentReminder.id)).where(
            PaymentReminder.created_at >= today_start,
        )
        
        result = await self.session.execute(query)
        count = result.scalar() or 0
        
        # Format: REM-YYYYMMDD-NNNN
        return f"REM-{date.today().strftime('%Y%m%d')}-{count + 1:04d}"