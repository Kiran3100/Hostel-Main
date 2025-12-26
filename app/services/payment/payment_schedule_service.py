# app/services/payment/payment_schedule_service.py
"""
Payment Schedule Service

Manages recurring payment schedules:
- Create/update/suspend schedules
- Generate scheduled payments
- Bulk schedule creation
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.payment import (
    PaymentScheduleRepository,
    PaymentRepository,
)
from app.schemas.payment import (
    PaymentSchedule,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleGeneration,
    ScheduledPaymentGenerated,
    BulkScheduleCreate,
    ScheduleSuspension,
    PaymentResponse,
)
from app.core.exceptions import ValidationException


class PaymentScheduleService:
    """
    High-level service for recurring payment schedules.

    Delegates heavy logic to PaymentScheduleRepository and PaymentRepository.
    """

    def __init__(
        self,
        schedule_repo: PaymentScheduleRepository,
        payment_repo: PaymentRepository,
    ) -> None:
        self.schedule_repo = schedule_repo
        self.payment_repo = payment_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_schedule(
        self,
        db: Session,
        request: ScheduleCreate,
    ) -> PaymentSchedule:
        obj = self.schedule_repo.create_schedule(
            db,
            data=request.model_dump(exclude_none=True),
        )
        return PaymentSchedule.model_validate(obj)

    def update_schedule(
        self,
        db: Session,
        schedule_id: UUID,
        request: ScheduleUpdate,
    ) -> PaymentSchedule:
        schedule = self.schedule_repo.get_by_id(db, schedule_id)
        if not schedule:
            raise ValidationException("Payment schedule not found")

        updated = self.schedule_repo.update_schedule(
            db,
            schedule,
            data=request.model_dump(exclude_none=True),
        )
        return PaymentSchedule.model_validate(updated)

    def suspend_schedule(
        self,
        db: Session,
        request: ScheduleSuspension,
    ) -> PaymentSchedule:
        schedule = self.schedule_repo.get_by_id(db, request.schedule_id)
        if not schedule:
            raise ValidationException("Payment schedule not found")

        updated = self.schedule_repo.suspend_schedule(
            db=db,
            schedule=schedule,
            reason=request.reason,
            suspend_from=request.suspend_from,
            suspend_to=request.suspend_to,
            skip_dues_during_suspension=request.skip_dues_during_suspension,
        )
        return PaymentSchedule.model_validate(updated)

    # -------------------------------------------------------------------------
    # Generation
    # -------------------------------------------------------------------------

    def generate_payments(
        self,
        db: Session,
        request: ScheduleGeneration,
    ) -> ScheduledPaymentGenerated:
        """
        Generate payments for a schedule within a period.
        """
        schedule = self.schedule_repo.get_by_id(db, request.schedule_id)
        if not schedule:
            raise ValidationException("Payment schedule not found")

        result = self.schedule_repo.generate_payments(
            db=db,
            schedule=schedule,
            from_date=request.from_date,
            to_date=request.to_date,
            skip_if_already_paid=request.skip_if_already_paid,
            send_notifications=request.send_notifications,
        )
        return ScheduledPaymentGenerated.model_validate(result)

    def bulk_create_schedules(
        self,
        db: Session,
        request: BulkScheduleCreate,
    ) -> List[PaymentSchedule]:
        """
        Create identical schedules for multiple students.
        """
        objs = self.schedule_repo.bulk_create_schedules(
            db=db,
            hostel_id=request.hostel_id,
            student_ids=request.student_ids,
            fee_type=request.fee_type,
            amount=request.amount,
            start_date=request.start_date,
            first_due_date=request.first_due_date,
        )
        return [PaymentSchedule.model_validate(o) for o in objs]