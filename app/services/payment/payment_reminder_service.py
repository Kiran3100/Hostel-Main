# app/services/payment/payment_reminder_service.py
"""
Payment Reminder Service

Manages configuration and sending of payment reminders.
"""

from __future__ import annotations

from typing import List
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.payment import PaymentReminderRepository, PaymentRepository
from app.schemas.payment import (
    ReminderConfig,
    ReminderLog,
    SendReminderRequest,
)
from app.core.exceptions import ValidationException
from app.services.workflows import NotificationWorkflowService


class PaymentReminderService:
    """
    High-level orchestration for payment reminders.

    Responsibilities:
    - Configure per-hostel reminder settings
    - Send manual/batch reminders
    - Log reminder events
    """

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
    ) -> ReminderConfig:
        """
        Create or update reminder configuration for a hostel.
        """
        existing = self.reminder_repo.get_config_for_hostel(db, hostel_id)
        payload = config.model_dump(exclude_none=True)
        payload["hostel_id"] = hostel_id

        if existing:
            obj = self.reminder_repo.update_config(db, existing, payload)
        else:
            obj = self.reminder_repo.create_config(db, payload)

        return ReminderConfig.model_validate(obj)

    def get_reminder_config(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> ReminderConfig:
        obj = self.reminder_repo.get_config_for_hostel(db, hostel_id)
        if not obj:
            # default disabled config
            return ReminderConfig(
                hostel_id=hostel_id,
                enabled=False,
                days_before_due=[],
                days_after_due=[],
                max_reminders_per_payment=0,
                channels=[],
            )
        return ReminderConfig.model_validate(obj)

    # -------------------------------------------------------------------------
    # Sending
    # -------------------------------------------------------------------------

    def send_reminders(
        self,
        db: Session,
        request: SendReminderRequest,
    ) -> List[ReminderLog]:
        """
        Send reminders either for specific payments or all due/overdue payments
        matching the request criteria.
        """
        logs: List[ReminderLog] = []
        now = datetime.utcnow()

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

        for payment in payments:
            log = self._send_single_reminder(db, payment.id, request, now)
            if log:
                logs.append(log)

        return logs

    def _send_single_reminder(
        self,
        db: Session,
        payment_id: UUID,
        request: SendReminderRequest,
        now: datetime,
    ) -> Optional[ReminderLog]:
        """
        Send a reminder for a single payment and create a log entry.
        """
        payment = self.payment_repo.get_by_id(db, payment_id)
        if not payment:
            return None

        # Create log first
        log_obj = self.reminder_repo.create_log(
            db=db,
            data={
                "payment_id": payment.id,
                "student_id": payment.student_id,
                "hostel_id": payment.hostel_id,
                "reminder_type": request.reminder_type,
                "sent_at": now,
                "channels": request.channels,
                "status": "pending",
            },
        )

        # Delegate channel sending to NotificationWorkflowService
        try:
            variables = {
                "amount": payment.amount,
                "due_date": payment.due_date.isoformat() if payment.due_date else None,
                "payment_reference": payment.payment_reference,
            }
            # Reuse generic approval/notification flow; or implement a dedicated one
            self.notification_workflow._create_and_queue_notification(  # type: ignore
                db=db,
                user_id=payment.payer_user_id,
                template_code=request.template_code or "PAYMENT_REMINDER",
                hostel_id=payment.hostel_id,
                variables=variables,
            )
            # Mark as sent
            updated = self.reminder_repo.update_log(
                db=db,
                log=log_obj,
                data={"status": "sent"},
            )
        except Exception as exc:
            updated = self.reminder_repo.update_log(
                db=db,
                log=log_obj,
                data={"status": "failed", "error_message": str(exc)},
            )

        return ReminderLog.model_validate(updated)