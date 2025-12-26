# app/services/payment/payment_reminder_service.py
"""
Payment Reminder Service

Manages configuration and sending of payment reminders:
- Configure reminder rules per hostel
- Send manual and automated reminders
- Track reminder delivery
- Prevent reminder spam
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.payment import PaymentReminderRepository, PaymentRepository
from app.schemas.payment import (
    ReminderConfig,
    ReminderLog,
    SendReminderRequest,
)
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)
from app.core.logging import LoggingContext, logger
from app.services.workflows import NotificationWorkflowService


class PaymentReminderService:
    """
    High-level orchestration for payment reminders.

    Responsibilities:
    - Configure per-hostel reminder settings
    - Send manual and batch reminders
    - Track reminder delivery and status
    - Prevent excessive reminder sending
    - Support multiple notification channels

    Delegates:
    - Reminder config to PaymentReminderRepository
    - Actual notification sending to NotificationWorkflowService
    """

    __slots__ = ("reminder_repo", "payment_repo", "notification_workflow")

    # Default reminder configuration
    DEFAULT_DAYS_BEFORE_DUE = [7, 3, 1]
    DEFAULT_DAYS_AFTER_DUE = [1, 3, 7, 15, 30]
    DEFAULT_MAX_REMINDERS = 10
    DEFAULT_CHANNELS = ["email", "sms"]

    # Spam prevention
    MIN_HOURS_BETWEEN_REMINDERS = 24

    def __init__(
        self,
        reminder_repo: PaymentReminderRepository,
        payment_repo: PaymentRepository,
        notification_workflow: NotificationWorkflowService,
    ) -> None:
        self.reminder_repo = reminder_repo
        self.payment_repo = payment_repo
        self.notification_workflow = notification_workflow

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def set_reminder_config(
        self,
        db: Session,
        hostel_id: UUID,
        config: ReminderConfig,
        updated_by: Optional[UUID] = None,
    ) -> ReminderConfig:
        """
        Create or update reminder configuration for a hostel.

        Args:
            db: Database session
            hostel_id: Hostel UUID
            config: Reminder configuration
            updated_by: UUID of user updating config

        Returns:
            ReminderConfig with saved configuration

        Raises:
            ValidationException: If configuration is invalid
        """
        self._validate_reminder_config(config)

        existing = self.reminder_repo.get_config_for_hostel(db, hostel_id)
        payload = config.model_dump(exclude_none=True)
        payload["hostel_id"] = hostel_id

        if updated_by:
            payload["updated_by"] = updated_by

        with LoggingContext(hostel_id=str(hostel_id)):
            if existing:
                obj = self.reminder_repo.update_config(db, existing, payload)
                logger.info(
                    f"Reminder config updated for hostel: {hostel_id}",
                    extra={"hostel_id": str(hostel_id)},
                )
            else:
                obj = self.reminder_repo.create_config(db, payload)
                logger.info(
                    f"Reminder config created for hostel: {hostel_id}",
                    extra={"hostel_id": str(hostel_id)},
                )

            return ReminderConfig.model_validate(obj)

    def _validate_reminder_config(self, config: ReminderConfig) -> None:
        """Validate reminder configuration."""
        if config.days_before_due:
            if any(d <= 0 for d in config.days_before_due):
                raise ValidationException(
                    "Days before due must be positive integers"
                )

        if config.days_after_due:
            if any(d < 0 for d in config.days_after_due):
                raise ValidationException(
                    "Days after due must be non-negative integers"
                )

        if config.max_reminders_per_payment is not None:
            if config.max_reminders_per_payment < 0:
                raise ValidationException(
                    "Max reminders per payment must be non-negative"
                )

        if config.channels:
            valid_channels = {"email", "sms", "push", "in_app"}
            invalid = set(config.channels) - valid_channels
            if invalid:
                raise ValidationException(
                    f"Invalid notification channels: {invalid}"
                )

    def get_reminder_config(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> ReminderConfig:
        """
        Get reminder configuration for a hostel.

        Returns default config if none exists.

        Args:
            db: Database session
            hostel_id: Hostel UUID

        Returns:
            ReminderConfig for the hostel
        """
        obj = self.reminder_repo.get_config_for_hostel(db, hostel_id)

        if not obj:
            # Return default configuration
            return ReminderConfig(
                hostel_id=hostel_id,
                enabled=False,
                days_before_due=self.DEFAULT_DAYS_BEFORE_DUE,
                days_after_due=self.DEFAULT_DAYS_AFTER_DUE,
                max_reminders_per_payment=self.DEFAULT_MAX_REMINDERS,
                channels=self.DEFAULT_CHANNELS,
            )

        return ReminderConfig.model_validate(obj)

    # -------------------------------------------------------------------------
    # Sending reminders
    # -------------------------------------------------------------------------

    def send_reminders(
        self,
        db: Session,
        request: SendReminderRequest,
    ) -> List[ReminderLog]:
        """
        Send reminders for payments.

        Can send to:
        - Specific payment IDs
        - All payments meeting criteria (hostel, overdue days, etc.)

        Args:
            db: Database session
            request: Reminder sending parameters

        Returns:
            List of ReminderLog entries for sent reminders

        Raises:
            ValidationException: If request is invalid
        """
        self._validate_send_reminder_request(request)

        logs: List[ReminderLog] = []
        now = datetime.utcnow()

        with LoggingContext(
            hostel_id=str(request.hostel_id) if request.hostel_id else None,
            reminder_type=request.reminder_type,
        ):
            # Determine target payments
            if request.payment_ids:
                payments = self.payment_repo.get_by_ids(db, request.payment_ids)
            else:
                payments = self.reminder_repo.get_payments_for_reminder(
                    db=db,
                    hostel_id=request.hostel_id,
                    min_days_overdue=request.min_days_overdue,
                    max_days_overdue=request.max_days_overdue,
                    reminder_type=request.reminder_type,
                )

            logger.info(
                f"Sending reminders to {len(payments)} payments",
                extra={"payment_count": len(payments)},
            )

            for payment in payments:
                log = self._send_single_reminder(db, payment, request, now)
                if log:
                    logs.append(log)

            logger.info(
                f"Reminders sent: {len(logs)} successful out of {len(payments)}",
                extra={
                    "sent_count": len(logs),
                    "total_count": len(payments),
                },
            )

            return logs

    def _validate_send_reminder_request(
        self, request: SendReminderRequest
    ) -> None:
        """Validate reminder sending request."""
        if not request.payment_ids and not request.hostel_id:
            raise ValidationException(
                "Either payment_ids or hostel_id must be provided"
            )

        if request.channels:
            valid_channels = {"email", "sms", "push", "in_app"}
            invalid = set(request.channels) - valid_channels
            if invalid:
                raise ValidationException(
                    f"Invalid notification channels: {invalid}"
                )

    def _send_single_reminder(
        self,
        db: Session,
        payment: Any,
        request: SendReminderRequest,
        now: datetime,
    ) -> Optional[ReminderLog]:
        """
        Send a reminder for a single payment.

        Args:
            db: Database session
            payment: Payment object
            request: Reminder request
            now: Current timestamp

        Returns:
            ReminderLog if reminder was sent, None if skipped
        """
        # Check if we should skip this payment
        if self._should_skip_reminder(db, payment, request):
            logger.debug(
                f"Skipping reminder for payment: {payment.id}",
                extra={"payment_id": str(payment.id)},
            )
            return None

        # Create log entry first
        log_obj = self.reminder_repo.create_log(
            db=db,
            data={
                "payment_id": payment.id,
                "student_id": payment.student_id,
                "hostel_id": payment.hostel_id,
                "reminder_type": request.reminder_type,
                "sent_at": now,
                "channels": request.channels or self.DEFAULT_CHANNELS,
                "status": "pending",
                "template_code": request.template_code or "PAYMENT_REMINDER",
            },
        )

        try:
            # Prepare notification variables
            variables = self._prepare_reminder_variables(payment)

            # Send through notification workflow
            for channel in (request.channels or self.DEFAULT_CHANNELS):
                self.notification_workflow._create_and_queue_notification(
                    db=db,
                    user_id=payment.payer_user_id,
                    template_code=request.template_code or "PAYMENT_REMINDER",
                    hostel_id=payment.hostel_id,
                    variables=variables,
                    channel=channel,
                )

            # Mark as sent
            updated = self.reminder_repo.update_log(
                db=db,
                log=log_obj,
                data={"status": "sent", "sent_at": datetime.utcnow()},
            )

            logger.debug(
                f"Reminder sent for payment: {payment.id}",
                extra={
                    "payment_id": str(payment.id),
                    "log_id": str(updated.id),
                },
            )

            return ReminderLog.model_validate(updated)

        except Exception as exc:
            # Mark as failed
            updated = self.reminder_repo.update_log(
                db=db,
                log=log_obj,
                data={
                    "status": "failed",
                    "error_message": str(exc),
                    "failed_at": datetime.utcnow(),
                },
            )

            logger.error(
                f"Failed to send reminder for payment {payment.id}: {str(exc)}",
                extra={"payment_id": str(payment.id)},
            )

            return ReminderLog.model_validate(updated)

    def _should_skip_reminder(
        self,
        db: Session,
        payment: Any,
        request: SendReminderRequest,
    ) -> bool:
        """
        Determine if reminder should be skipped for a payment.

        Reasons to skip:
        - Payment already completed
        - Too many reminders already sent
        - Reminder sent too recently (spam prevention)
        - Student has opted out of reminders
        """
        # Skip completed payments
        if payment.status.value in {"completed", "refunded"}:
            return True

        # Check reminder config for hostel
        config = self.get_reminder_config(db, payment.hostel_id)
        if not config.enabled:
            return True

        # Check max reminders limit
        reminder_count = self.reminder_repo.count_reminders_for_payment(
            db, payment.id
        )
        if reminder_count >= config.max_reminders_per_payment:
            logger.debug(
                f"Max reminders reached for payment {payment.id}: "
                f"{reminder_count}/{config.max_reminders_per_payment}"
            )
            return True

        # Check time since last reminder (spam prevention)
        last_reminder = self.reminder_repo.get_last_reminder_for_payment(
            db, payment.id
        )
        if last_reminder:
            hours_since = (
                datetime.utcnow() - last_reminder.sent_at
            ).total_seconds() / 3600
            if hours_since < self.MIN_HOURS_BETWEEN_REMINDERS:
                logger.debug(
                    f"Reminder sent too recently for payment {payment.id}: "
                    f"{hours_since:.1f} hours ago"
                )
                return True

        return False

    def _prepare_reminder_variables(self, payment: Any) -> Dict[str, Any]:
        """Prepare template variables for reminder notification."""
        days_overdue = 0
        if payment.due_date:
            days_overdue = (date.today() - payment.due_date).days

        return {
            "payment_reference": payment.payment_reference,
            "amount": float(payment.amount),
            "currency": payment.currency or "INR",
            "due_date": payment.due_date.isoformat() if payment.due_date else None,
            "days_overdue": max(0, days_overdue),
            "fee_type": payment.fee_type,
            "student_name": payment.student.full_name if hasattr(payment, "student") else "",
            "payment_url": f"/payments/{payment.id}",
        }

    # -------------------------------------------------------------------------
    # Automated reminder processing
    # -------------------------------------------------------------------------

    def process_automated_reminders(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Process automated reminders based on hostel configurations.

        This is typically run as a scheduled job.

        Args:
            db: Database session
            hostel_id: Optional hostel filter
            dry_run: If True, only count reminders without sending

        Returns:
            Dictionary with processing statistics
        """
        stats = {
            "hostels_processed": 0,
            "reminders_sent": 0,
            "reminders_skipped": 0,
            "errors": [],
        }

        # Get all hostels with reminder configs enabled
        if hostel_id:
            configs = [self.reminder_repo.get_config_for_hostel(db, hostel_id)]
        else:
            configs = self.reminder_repo.get_all_enabled_configs(db)

        for config in configs:
            if not config or not config.enabled:
                continue

            try:
                hostel_stats = self._process_reminders_for_hostel(
                    db=db,
                    config=config,
                    dry_run=dry_run,
                )
                stats["reminders_sent"] += hostel_stats["sent"]
                stats["reminders_skipped"] += hostel_stats["skipped"]
                stats["hostels_processed"] += 1

            except Exception as e:
                logger.error(
                    f"Failed to process reminders for hostel {config.hostel_id}: {str(e)}"
                )
                stats["errors"].append({
                    "hostel_id": str(config.hostel_id),
                    "error": str(e),
                })

        logger.info(
            f"Automated reminder processing completed: "
            f"{stats['reminders_sent']} sent, {stats['reminders_skipped']} skipped "
            f"across {stats['hostels_processed']} hostels"
        )

        return stats

    def _process_reminders_for_hostel(
        self,
        db: Session,
        config: Any,
        dry_run: bool,
    ) -> Dict[str, int]:
        """Process reminders for a single hostel based on its config."""
        stats = {"sent": 0, "skipped": 0}

        # Process "before due" reminders
        for days in config.days_before_due:
            request = SendReminderRequest(
                hostel_id=config.hostel_id,
                reminder_type="before_due",
                min_days_overdue=-days,
                max_days_overdue=-days,
                channels=config.channels,
            )

            if not dry_run:
                logs = self.send_reminders(db, request)
                stats["sent"] += len(logs)
            else:
                # Just count
                payments = self.reminder_repo.get_payments_for_reminder(
                    db=db,
                    hostel_id=config.hostel_id,
                    min_days_overdue=-days,
                    max_days_overdue=-days,
                    reminder_type="before_due",
                )
                stats["sent"] += len(payments)

        # Process "after due" reminders
        for days in config.days_after_due:
            request = SendReminderRequest(
                hostel_id=config.hostel_id,
                reminder_type="overdue",
                min_days_overdue=days,
                max_days_overdue=days,
                channels=config.channels,
            )

            if not dry_run:
                logs = self.send_reminders(db, request)
                stats["sent"] += len(logs)
            else:
                payments = self.reminder_repo.get_payments_for_reminder(
                    db=db,
                    hostel_id=config.hostel_id,
                    min_days_overdue=days,
                    max_days_overdue=days,
                    reminder_type="overdue",
                )
                stats["sent"] += len(payments)

        return stats

    # -------------------------------------------------------------------------
    # Reminder logs & history
    # -------------------------------------------------------------------------

    def get_reminder_log(
        self,
        db: Session,
        log_id: UUID,
    ) -> ReminderLog:
        """
        Get a specific reminder log entry.

        Args:
            db: Database session
            log_id: Reminder log UUID

        Returns:
            ReminderLog details

        Raises:
            NotFoundException: If log not found
        """
        obj = self.reminder_repo.get_log_by_id(db, log_id)
        if not obj:
            raise NotFoundException(f"Reminder log not found: {log_id}")

        return ReminderLog.model_validate(obj)

    def get_reminders_for_payment(
        self,
        db: Session,
        payment_id: UUID,
    ) -> List[ReminderLog]:
        """
        Get all reminder logs for a payment.

        Args:
            db: Database session
            payment_id: Payment UUID

        Returns:
            List of ReminderLog entries
        """
        objs = self.reminder_repo.get_logs_for_payment(db, payment_id)
        return [ReminderLog.model_validate(o) for o in objs]

    def get_reminders_for_student(
        self,
        db: Session,
        student_id: UUID,
        limit: int = 50,
    ) -> List[ReminderLog]:
        """
        Get reminder history for a student.

        Args:
            db: Database session
            student_id: Student UUID
            limit: Maximum number of logs to return

        Returns:
            List of ReminderLog entries
        """
        objs = self.reminder_repo.get_logs_for_student(
            db, student_id, limit=limit
        )
        return [ReminderLog.model_validate(o) for o in objs]

    def get_reminder_statistics(
        self,
        db: Session,
        hostel_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get reminder statistics for a hostel.

        Args:
            db: Database session
            hostel_id: Hostel UUID
            days: Number of days to include in statistics

        Returns:
            Dictionary with reminder statistics
        """
        since = datetime.utcnow() - timedelta(days=days)

        return self.reminder_repo.get_reminder_statistics(
            db=db,
            hostel_id=hostel_id,
            since=since,
        )