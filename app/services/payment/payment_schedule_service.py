# app/services/payment/payment_schedule_service.py
from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.repositories.transactions import PaymentRepository
from app.repositories.core import HostelRepository, StudentRepository
from app.schemas.common.enums import FeeType, PaymentType, PaymentMethod, PaymentStatus
from app.schemas.payment.payment_schedule import (
    PaymentSchedule,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleGeneration,
    ScheduledPaymentGenerated,
)
from app.services.common import UnitOfWork, errors


class ScheduleStore(Protocol):
    """
    Storage for payment schedules (PaymentSchedule-like dicts).
    """

    def get_schedule(self, schedule_id: UUID) -> Optional[dict]: ...
    def save_schedule(self, schedule_id: UUID, data: dict) -> None: ...
    def list_schedules_for_student(self, student_id: UUID) -> List[dict]: ...


class PaymentScheduleService:
    """
    Payment schedules:

    - Create/update schedules
    - Fetch schedule
    - Generate scheduled payments via PaymentRepository
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: ScheduleStore,
    ) -> None:
        self._session_factory = session_factory
        self._store = store

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _period_months(self, fee_type: FeeType) -> int:
        mapping = {
            FeeType.MONTHLY: 1,
            FeeType.QUARTERLY: 3,
            FeeType.HALF_YEARLY: 6,
            FeeType.YEARLY: 12,
        }
        return mapping.get(fee_type, 1)

    def _add_months(self, d: Date, months: int) -> Date:
        month = d.month - 1 + months
        year = d.year + month // 12
        month = month % 12 + 1
        day = min(
            d.day,
            [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
             31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
        )
        return Date(year, month, day)

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create_schedule(self, data: ScheduleCreate) -> PaymentSchedule:
        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            student = student_repo.get(data.student_id)
            if student is None or not getattr(student, "user", None):
                raise errors.NotFoundError(f"Student {data.student_id} not found")

            schedule_id = uuid4()
            record = {
                "id": schedule_id,
                "created_at": None,
                "updated_at": None,
                "student_id": data.student_id,
                "student_name": student.user.full_name,
                "hostel_id": data.hostel_id,
                "hostel_name": hostel.name,
                "fee_type": data.fee_type,
                "amount": data.amount,
                "start_date": data.start_date,
                "end_date": data.end_date,
                "next_due_date": data.first_due_date,
                "auto_generate_invoice": data.auto_generate_invoice,
                "is_active": True,
            }
            self._store.save_schedule(schedule_id, record)
            return PaymentSchedule.model_validate(record)

    def get_schedule(self, schedule_id: UUID) -> PaymentSchedule:
        record = self._store.get_schedule(schedule_id)
        if not record:
            raise errors.NotFoundError(f"PaymentSchedule {schedule_id} not found")
        return PaymentSchedule.model_validate(record)

    def update_schedule(self, schedule_id: UUID, data: ScheduleUpdate) -> PaymentSchedule:
        record = self._store.get_schedule(schedule_id)
        if not record:
            raise errors.NotFoundError(f"PaymentSchedule {schedule_id} not found")

        mapping = data.model_dump(exclude_unset=True)
        for field, value in mapping.items():
            record[field] = value
        self._store.save_schedule(schedule_id, record)
        return PaymentSchedule.model_validate(record)

    # ------------------------------------------------------------------ #
    # Generation
    # ------------------------------------------------------------------ #
    def generate_scheduled_payments(self, data: ScheduleGeneration) -> ScheduledPaymentGenerated:
        record = self._store.get_schedule(data.schedule_id)
        if not record:
            raise errors.NotFoundError(f"PaymentSchedule {data.schedule_id} not found")

        schedule = PaymentSchedule.model_validate(record)
        months = self._period_months(schedule.fee_type)

        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)

            payments_generated: List[UUID] = []
            payments_skipped = 0

            current_due = schedule.next_due_date
            while current_due <= data.generate_to_date:
                if current_due < data.generate_from_date:
                    current_due = self._add_months(current_due, months)
                    continue

                # Check if a payment already exists for this student & due_date
                existing = pay_repo.get_multi(
                    skip=0,
                    limit=1,
                    filters={
                        "student_id": schedule.student_id,
                        "hostel_id": schedule.hostel_id,
                        "due_date": current_due,
                    },
                )
                if existing and data.skip_if_already_paid:
                    payments_skipped += 1
                else:
                    payload = {
                        "payer_id": None,
                        "hostel_id": schedule.hostel_id,
                        "student_id": schedule.student_id,
                        "booking_id": None,
                        "payment_type": PaymentType.RENT,
                        "amount": schedule.amount,
                        "currency": "INR",
                        "payment_period_start": current_due,
                        "payment_period_end": None,
                        "payment_method": PaymentMethod.PAYMENT_GATEWAY,
                        "payment_gateway": "razorpay",
                        "payment_status": PaymentStatus.PENDING,
                        "due_date": current_due,
                    }
                    p = pay_repo.create(payload)  # type: ignore[arg-type]
                    payments_generated.append(p.id)

                current_due = self._add_months(current_due, months)

            # Update next_due_date on schedule
            record["next_due_date"] = current_due
            self._store.save_schedule(data.schedule_id, record)
            uow.commit()

        return ScheduledPaymentGenerated(
            schedule_id=data.schedule_id,
            payments_generated=len(payments_generated),
            payments_skipped=payments_skipped,
            generated_payment_ids=payments_generated,
            next_generation_date=record["next_due_date"],
        )