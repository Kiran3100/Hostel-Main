# app/services/payment/payment_reminder_service.py
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.repositories.transactions import PaymentRepository
from app.repositories.core import StudentRepository, HostelRepository, UserRepository
from app.schemas.common.enums import PaymentStatus
from app.schemas.payment.payment_reminder import (
    ReminderConfig,
    ReminderLog,
    SendReminderRequest,
    ReminderBatch,
    ReminderStats,
)
from app.services.common import UnitOfWork, errors


class ReminderConfigStore(Protocol):
    """
    Storage for ReminderConfig per hostel.
    """

    def get_config(self, hostel_id: UUID) -> Optional[dict]: ...
    def save_config(self, hostel_id: UUID, data: dict) -> None: ...


class ReminderLogStore(Protocol):
    """
    Storage for ReminderLog entries.
    """

    def save_log(self, record: dict) -> dict: ...
    def list_logs_for_period(self, hostel_id: UUID, start: date, end: date) -> List[dict]: ...


class ReminderSender(Protocol):
    """
    Abstraction for sending reminders (email/SMS/push/notification).
    """

    def send(
        self,
        *,
        student_id: UUID,
        student_email: str,
        student_phone: str,
        channel: str,
        subject: Optional[str],
        message: str,
    ) -> bool: ...


class PaymentReminderService:
    """
    Payment reminder service:

    - Manage ReminderConfig per hostel
    - Send manual reminders (per payment/student/hostel)
    - Basic stats over reminders
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        config_store: ReminderConfigStore,
        log_store: ReminderLogStore,
        sender: ReminderSender,
    ) -> None:
        self._session_factory = session_factory
        self._config_store = config_store
        self._log_store = log_store
        self._sender = sender

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def get_config(self, hostel_id: UUID) -> ReminderConfig:
        record = self._config_store.get_config(hostel_id)
        if record:
            return ReminderConfig.model_validate(record)

        cfg = ReminderConfig(
            id=None,
            created_at=None,
            updated_at=None,
            hostel_id=hostel_id,
        )
        self._config_store.save_config(hostel_id, cfg.model_dump())
        return cfg

    def set_config(self, cfg: ReminderConfig) -> None:
        self._config_store.save_config(cfg.hostel_id, cfg.model_dump())

    # ------------------------------------------------------------------ #
    # Sending
    # ------------------------------------------------------------------ #
    def send_reminders(self, req: SendReminderRequest) -> ReminderBatch:
        """
        Send reminders based on filters in SendReminderRequest.

        This is a simplified implementation that:
        - Finds PENDING payments (optionally overdue-only).
        - Sends reminders via configured channels.
        - Logs ReminderLog entries.
        """
        now = self._now()
        batch_id = uuid4()

        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            student_repo = self._get_student_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            payments = self._select_target_payments(uow, req)
            total_payments = len(payments)

            reminders_sent = reminders_failed = 0
            email_sent = sms_sent = push_sent = 0

            for p in payments:
                if p.student_id is None:
                    continue
                st = student_repo.get(p.student_id)
                if st is None or not getattr(st, "user", None):
                    continue
                user = st.user
                subject = "Payment Reminder"
                base_message = req.custom_message or "You have a pending payment."

                for ch in req.channels:
                    ok = self._sender.send(
                        student_id=st.id,
                        student_email=user.email,
                        student_phone=getattr(user, "phone", ""),
                        channel=ch,
                        subject=subject if ch == "email" else None,
                        message=base_message,
                    )
                    if ok:
                        reminders_sent += 1
                        if ch == "email":
                            email_sent += 1
                        elif ch == "sms":
                            sms_sent += 1
                        elif ch == "push":
                            push_sent += 1
                        self._log_reminder(
                            p=p,
                            student=st,
                            user=user,
                            reminder_type=req.reminder_type,
                            channel=ch,
                            message_preview=base_message[:100],
                        )
                    else:
                        reminders_failed += 1

        return ReminderBatch(
            batch_id=batch_id,
            total_payments=total_payments,
            reminders_sent=reminders_sent,
            reminders_failed=reminders_failed,
            email_sent=email_sent,
            sms_sent=sms_sent,
            push_sent=push_sent,
            started_at=now,
            completed_at=self._now(),
            status="completed",
        )

    # Helpers for sending
    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _select_target_payments(
        self,
        uow: UnitOfWork,
        req: SendReminderRequest,
    ) -> List:
        pay_repo = self._get_payment_repo(uow)

        filters: Dict[str, object] = {"payment_status": PaymentStatus.PENDING}
        if req.payment_id:
            filters["id"] = req.payment_id
        if req.student_id:
            filters["student_id"] = req.student_id
        if req.hostel_id:
            filters["hostel_id"] = req.hostel_id

        payments = pay_repo.get_multi(
            skip=0,
            limit=None,  # type: ignore[arg-type]
            filters=filters,
        )
        # For overdue reminders, restrict to past-due
        if req.reminder_type in ("overdue", "final_notice"):
            today = date.today()
            payments = [p for p in payments if p.due_date and p.due_date < today]
        return list(payments)

    def _log_reminder(
        self,
        *,
        p,
        student,
        user,
        reminder_type: str,
        channel: str,
        message_preview: str,
    ) -> None:
        record = {
            "id": uuid4(),
            "created_at": self._now(),
            "updated_at": self._now(),
            "payment_id": p.id,
            "payment_reference": str(p.id),
            "student_id": student.id,
            "student_name": user.full_name,
            "student_email": user.email,
            "student_phone": getattr(user, "phone", ""),
            "reminder_type": reminder_type,
            "reminder_channel": channel,
            "sent_at": self._now(),
            "delivery_status": "sent",
            "subject": None,
            "message_preview": message_preview,
            "opened": False,
            "clicked": False,
        }
        self._log_store.save_log(record)

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def get_stats(self, hostel_id: UUID, *, period_start: date, period_end: date) -> ReminderStats:
        logs = self._log_store.list_logs_for_period(hostel_id, period_start, period_end)
        total = len(logs)

        due_soon = sum(1 for l in logs if l.get("reminder_type") == "due_soon")
        overdue = sum(1 for l in logs if l.get("reminder_type") == "overdue")
        final_notice = sum(1 for l in logs if l.get("reminder_type") == "final_notice")

        email_count = sum(1 for l in logs if l.get("reminder_channel") == "email")
        sms_count = sum(1 for l in logs if l.get("reminder_channel") == "sms")
        push_count = sum(1 for l in logs if l.get("reminder_channel") == "push")

        # Effectiveness metrics require link to payments;
        # here we just return zeros as placeholders.
        return ReminderStats(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            total_reminders_sent=total,
            due_soon_reminders=due_soon,
            overdue_reminders=overdue,
            final_notices=final_notice,
            email_reminders=email_count,
            sms_reminders=sms_count,
            push_reminders=push_count,
            payment_rate_after_reminder=Decimal("0"),
            average_days_to_payment=Decimal("0"),
        )