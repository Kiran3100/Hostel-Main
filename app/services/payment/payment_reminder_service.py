"""
Payment Reminder Service.

Multi-channel reminder system with scheduling, template rendering,
engagement tracking, and escalation workflows.
"""

from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ReminderError
from app.models.payment.payment import Payment
from app.models.payment.payment_reminder import (
    PaymentReminder,
    ReminderStatus,
    ReminderType,
)
from app.repositories.payment.payment_reminder_repository import (
    PaymentReminderRepository,
)
from app.repositories.payment.payment_repository import PaymentRepository
from app.schemas.common.enums import PaymentStatus


class PaymentReminderService:
    """
    Service for payment reminder operations.
    
    Features:
    - Multi-channel delivery (Email, SMS, Push)
    - Template-based messaging
    - Scheduled reminders
    - Engagement tracking
    - Escalation workflows
    - Retry logic
    """

    # Reminder configuration
    REMINDER_SCHEDULE = {
        ReminderType.BEFORE_DUE: -7,  # 7 days before
        ReminderType.ON_DUE: 0,  # On due date
        ReminderType.AFTER_DUE: 1,  # 1 day after
        ReminderType.OVERDUE: 7,  # 7 days overdue
    }
    
    MAX_REMINDERS = 5
    RETRY_ATTEMPTS = 3

    def __init__(
        self,
        session: AsyncSession,
        reminder_repo: PaymentReminderRepository,
        payment_repo: PaymentRepository,
        # In production, inject email/SMS/push services
        # email_service: EmailService,
        # sms_service: SMSService,
        # push_service: PushNotificationService,
    ):
        """Initialize reminder service."""
        self.session = session
        self.reminder_repo = reminder_repo
        self.payment_repo = payment_repo
        # self.email_service = email_service
        # self.sms_service = sms_service
        # self.push_service = push_service

    # ==================== Reminder Scheduling ====================

    async def schedule_payment_reminders(
        self,
        payment: Payment,
        channels: Optional[list[str]] = None,
    ) -> list[PaymentReminder]:
        """
        Schedule all reminders for a payment.
        
        Creates reminder records for:
        - Before due date
        - On due date
        - After due date (if unpaid)
        - Overdue escalation
        
        Args:
            payment: Payment to schedule reminders for
            channels: Channels to use (email, sms, push)
            
        Returns:
            List of created reminder records
        """
        if not payment.due_date:
            return []
        
        if not channels:
            channels = ["email", "sms"]
        
        reminders = []
        
        try:
            async with self.session.begin_nested():
                # Create reminders for each type
                for reminder_type, days_offset in self.REMINDER_SCHEDULE.items():
                    scheduled_date = payment.due_date + timedelta(days=days_offset)
                    scheduled_datetime = datetime.combine(
                        scheduled_date,
                        datetime.min.time().replace(hour=9)  # 9 AM
                    )
                    
                    # Skip if in the past
                    if scheduled_datetime < datetime.utcnow():
                        continue
                    
                    # Get student details (would fetch from student service)
                    student_name = "Student Name"  # TODO: Fetch from student
                    student_email = "student@example.com"  # TODO
                    student_phone = "+911234567890"  # TODO
                    
                    reminder = await self.reminder_repo.create_reminder(
                        payment_id=payment.id,
                        student_id=payment.student_id,
                        hostel_id=payment.hostel_id,
                        reminder_type=reminder_type,
                        reminder_number=len(reminders) + 1,
                        recipient_name=student_name,
                        recipient_email=student_email if "email" in channels else None,
                        recipient_phone=student_phone if "sms" in channels else None,
                        scheduled_for=scheduled_datetime,
                        template_id=f"payment_reminder_{reminder_type.value}",
                        template_variables={
                            "student_name": student_name,
                            "payment_amount": float(payment.amount),
                            "payment_type": payment.payment_type.value,
                            "due_date": payment.due_date.isoformat(),
                            "payment_reference": payment.payment_reference,
                        },
                    )
                    
                    reminders.append(reminder)
                
                await self.session.commit()
                return reminders
                
        except Exception as e:
            await self.session.rollback()
            raise ReminderError(f"Failed to schedule reminders: {str(e)}")

    async def schedule_manual_reminder(
        self,
        payment_id: UUID,
        scheduled_for: datetime,
        channels: list[str],
        custom_message: Optional[str] = None,
    ) -> PaymentReminder:
        """
        Schedule a manual reminder.
        
        Args:
            payment_id: Payment ID
            scheduled_for: When to send
            channels: Delivery channels
            custom_message: Custom message override
            
        Returns:
            Created reminder
        """
        try:
            async with self.session.begin_nested():
                payment = await self.payment_repo.get_by_id(payment_id)
                if not payment:
                    raise ReminderError(f"Payment not found: {payment_id}")
                
                # Get reminder count
                existing = await self.reminder_repo.find_by_payment(payment_id)
                
                reminder = await self.reminder_repo.create_reminder(
                    payment_id=payment_id,
                    student_id=payment.student_id,
                    hostel_id=payment.hostel_id,
                    reminder_type=ReminderType.MANUAL,
                    reminder_number=len(existing) + 1,
                    recipient_name="Student",  # TODO: Fetch
                    recipient_email="student@example.com" if "email" in channels else None,
                    recipient_phone="+911234567890" if "sms" in channels else None,
                    scheduled_for=scheduled_for,
                    template_variables={
                        "custom_message": custom_message,
                    } if custom_message else None,
                )
                
                await self.session.commit()
                return reminder
                
        except Exception as e:
            await self.session.rollback()
            raise ReminderError(f"Failed to schedule manual reminder: {str(e)}")

    # ==================== Reminder Delivery ====================

    async def send_reminder(
        self,
        reminder_id: UUID,
    ) -> dict[str, Any]:
        """
        Send a scheduled reminder.
        
        Args:
            reminder_id: Reminder to send
            
        Returns:
            Delivery result
        """
        try:
            async with self.session.begin_nested():
                reminder = await self.reminder_repo.get_by_id(reminder_id)
                if not reminder:
                    raise ReminderError(f"Reminder not found: {reminder_id}")
                
                if reminder.reminder_status != ReminderStatus.PENDING:
                    raise ReminderError(
                        f"Reminder already sent: {reminder.reminder_status}"
                    )
                
                # Get payment details
                payment = await self.payment_repo.get_by_id(reminder.payment_id)
                if not payment:
                    raise ReminderError(f"Payment not found: {reminder.payment_id}")
                
                # Skip if payment is already completed
                if payment.payment_status == PaymentStatus.COMPLETED:
                    await self.reminder_repo.update(
                        reminder_id,
                        {"reminder_status": ReminderStatus.CANCELLED},
                    )
                    return {"status": "cancelled", "reason": "payment_completed"}
                
                # Render template
                message = await self._render_reminder_message(reminder, payment)
                
                # Send through channels
                email_sent = False
                sms_sent = False
                push_sent = False
                
                email_message_id = None
                sms_message_id = None
                push_notification_id = None
                
                # Email
                if reminder.recipient_email:
                    email_result = await self._send_email(
                        to=reminder.recipient_email,
                        subject=message["subject"],
                        body=message["body"],
                    )
                    email_sent = email_result["success"]
                    email_message_id = email_result.get("message_id")
                
                # SMS
                if reminder.recipient_phone:
                    sms_result = await self._send_sms(
                        to=reminder.recipient_phone,
                        message=message["sms_text"],
                    )
                    sms_sent = sms_result["success"]
                    sms_message_id = sms_result.get("message_id")
                
                # Push Notification
                push_result = await self._send_push_notification(
                    student_id=reminder.student_id,
                    title=message["subject"],
                    body=message["push_text"],
                )
                push_sent = push_result["success"]
                push_notification_id = push_result.get("notification_id")
                
                # Mark as sent
                await self.reminder_repo.mark_reminder_sent(
                    reminder_id=reminder_id,
                    sent_via_email=email_sent,
                    sent_via_sms=sms_sent,
                    sent_via_push=push_sent,
                    email_message_id=email_message_id,
                    sms_message_id=sms_message_id,
                    push_notification_id=push_notification_id,
                )
                
                # Update payment reminder count
                await self.payment_repo.increment_reminder_count(payment.id)
                
                await self.session.commit()
                
                return {
                    "status": "sent",
                    "reminder_id": str(reminder_id),
                    "channels": {
                        "email": email_sent,
                        "sms": sms_sent,
                        "push": push_sent,
                    },
                }
                
        except Exception as e:
            await self.session.rollback()
            
            # Mark as failed
            try:
                await self.reminder_repo.mark_reminder_failed(
                    reminder_id=reminder_id,
                    error_message=str(e),
                )
            except:
                pass
            
            raise ReminderError(f"Failed to send reminder: {str(e)}")

    async def send_pending_reminders(
        self,
        hostel_id: Optional[UUID] = None,
        batch_size: int = 100,
    ) -> dict[str, Any]:
        """
        Send all pending reminders.
        
        This should be run as a scheduled job (every hour or so).
        
        Args:
            hostel_id: Optional hostel filter
            batch_size: Maximum reminders to send
            
        Returns:
            Sending summary
        """
        pending_reminders = await self.reminder_repo.find_pending_reminders(
            hostel_id=hostel_id,
        )
        
        # Limit batch size
        reminders_to_send = pending_reminders[:batch_size]
        
        results = {
            "total_pending": len(pending_reminders),
            "processed": 0,
            "sent": 0,
            "failed": 0,
            "cancelled": 0,
            "errors": [],
        }
        
        for reminder in reminders_to_send:
            try:
                result = await self.send_reminder(reminder.id)
                results["processed"] += 1
                
                if result["status"] == "sent":
                    results["sent"] += 1
                elif result["status"] == "cancelled":
                    results["cancelled"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "reminder_id": str(reminder.id),
                    "error": str(e),
                })
        
        return results

    # ==================== Engagement Tracking ====================

    async def track_email_opened(
        self,
        reminder_id: Optional[UUID] = None,
        email_message_id: Optional[str] = None,
    ) -> PaymentReminder:
        """
        Track when email reminder is opened.
        
        Args:
            reminder_id: Reminder ID
            email_message_id: Email message ID
            
        Returns:
            Updated reminder
        """
        if not reminder_id and email_message_id:
            # Find by message ID
            reminder = await self.reminder_repo.find_by_email_message_id(
                email_message_id
            )
            reminder_id = reminder.id if reminder else None
        
        if not reminder_id:
            raise ReminderError("Reminder not found")
        
        return await self.reminder_repo.track_email_opened(reminder_id)

    async def track_email_clicked(
        self,
        reminder_id: Optional[UUID] = None,
        email_message_id: Optional[str] = None,
    ) -> PaymentReminder:
        """Track when email link is clicked."""
        if not reminder_id and email_message_id:
            reminder = await self.reminder_repo.find_by_email_message_id(
                email_message_id
            )
            reminder_id = reminder.id if reminder else None
        
        if not reminder_id:
            raise ReminderError("Reminder not found")
        
        return await self.reminder_repo.track_email_clicked(reminder_id)

    async def track_sms_delivered(
        self,
        reminder_id: Optional[UUID] = None,
        sms_message_id: Optional[str] = None,
    ) -> PaymentReminder:
        """Track when SMS is delivered."""
        if not reminder_id and sms_message_id:
            reminder = await self.reminder_repo.find_by_sms_message_id(
                sms_message_id
            )
            reminder_id = reminder.id if reminder else None
        
        if not reminder_id:
            raise ReminderError("Reminder not found")
        
        return await self.reminder_repo.track_sms_delivered(reminder_id)

    async def track_push_clicked(
        self,
        reminder_id: UUID,
    ) -> PaymentReminder:
        """Track when push notification is clicked."""
        return await self.reminder_repo.track_push_clicked(reminder_id)

    # ==================== Retry Logic ====================

    async def retry_failed_reminders(
        self,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Retry failed reminders.
        
        Args:
            max_retries: Maximum retry attempts
            
        Returns:
            Retry summary
        """
        failed_reminders = await self.reminder_repo.find_failed_reminders(
            max_retries=max_retries,
        )
        
        results = {
            "total_failed": len(failed_reminders),
            "retried": 0,
            "succeeded": 0,
            "still_failed": 0,
        }
        
        for reminder in failed_reminders:
            try:
                # Increment retry count
                await self.reminder_repo.increment_retry_count(reminder.id)
                
                # Attempt to send again
                result = await self.send_reminder(reminder.id)
                
                results["retried"] += 1
                if result["status"] == "sent":
                    results["succeeded"] += 1
                    
            except Exception:
                results["still_failed"] += 1
        
        return results

    # ==================== Analytics ====================

    async def get_reminder_statistics(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get reminder statistics."""
        return await self.reminder_repo.calculate_reminder_statistics(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_reminder_effectiveness(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get reminder effectiveness metrics."""
        return await self.reminder_repo.get_reminder_effectiveness(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_channel_performance(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get performance comparison across channels."""
        return await self.reminder_repo.get_channel_performance(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    # ==================== Helper Methods ====================

    async def _render_reminder_message(
        self,
        reminder: PaymentReminder,
        payment: Payment,
    ) -> dict[str, str]:
        """
        Render reminder message from template.
        
        In production, this would use a template engine.
        """
        variables = reminder.template_variables or {}
        
        # Get template based on reminder type
        templates = {
            ReminderType.BEFORE_DUE: {
                "subject": "Upcoming Payment Due - {payment_type}",
                "body": """
                    Dear {student_name},
                    
                    This is a friendly reminder that your {payment_type} payment of 
                    ₹{payment_amount} is due on {due_date}.
                    
                    Payment Reference: {payment_reference}
                    
                    Please make the payment before the due date to avoid late fees.
                    
                    Thanks,
                    Hostel Management
                """,
                "sms_text": "Payment of ₹{payment_amount} due on {due_date}. Ref: {payment_reference}",
                "push_text": "Payment due on {due_date}",
            },
            ReminderType.ON_DUE: {
                "subject": "Payment Due Today - {payment_type}",
                "body": """
                    Dear {student_name},
                    
                    Your {payment_type} payment of ₹{payment_amount} is due TODAY.
                    
                    Payment Reference: {payment_reference}
                    
                    Please make the payment today to avoid late fees.
                    
                    Thanks,
                    Hostel Management
                """,
                "sms_text": "Payment of ₹{payment_amount} due TODAY. Ref: {payment_reference}",
                "push_text": "Payment due today!",
            },
            ReminderType.OVERDUE: {
                "subject": "URGENT: Overdue Payment - {payment_type}",
                "body": """
                    Dear {student_name},
                    
                    Your {payment_type} payment of ₹{payment_amount} is OVERDUE.
                    Due date was: {due_date}
                    
                    Payment Reference: {payment_reference}
                    
                    Please make the payment immediately to avoid penalties.
                    
                    Thanks,
                    Hostel Management
                """,
                "sms_text": "URGENT: Payment of ₹{payment_amount} is OVERDUE. Ref: {payment_reference}",
                "push_text": "Overdue payment - Please pay now",
            },
        }
        
        template = templates.get(
            reminder.reminder_type,
            templates[ReminderType.BEFORE_DUE]
        )
        
        # Simple variable substitution
        rendered = {}
        for key, text in template.items():
            rendered[key] = text.format(**variables)
        
        return rendered

    async def _send_email(
        self,
        to: str,
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        """
        Send email reminder.
        
        In production, integrate with actual email service.
        """
        # Mock implementation
        # In production: await self.email_service.send(to, subject, body)
        
        return {
            "success": True,
            "message_id": f"email_{datetime.utcnow().timestamp()}",
        }

    async def _send_sms(
        self,
        to: str,
        message: str,
    ) -> dict[str, Any]:
        """
        Send SMS reminder.
        
        In production, integrate with Twilio/AWS SNS/etc.
        """
        # Mock implementation
        # In production: await self.sms_service.send(to, message)
        
        return {
            "success": True,
            "message_id": f"sms_{datetime.utcnow().timestamp()}",
        }

    async def _send_push_notification(
        self,
        student_id: UUID,
        title: str,
        body: str,
    ) -> dict[str, Any]:
        """
        Send push notification.
        
        In production, integrate with Firebase/OneSignal/etc.
        """
        # Mock implementation
        # In production: await self.push_service.send(student_id, title, body)
        
        return {
            "success": True,
            "notification_id": f"push_{datetime.utcnow().timestamp()}",
        }