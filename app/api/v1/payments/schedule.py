# app/api/v1/payments/schedule.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.payment import PaymentScheduleService
from app.schemas.payment.payment_schedule import (
    PaymentSchedule,
    ScheduleCreate,
    ScheduleUpdate,
    BulkScheduleCreate,
    ScheduleGeneration,
    ScheduledPaymentGenerated,
    ScheduleSuspension,
)
from . import CurrentUser, get_current_admin_or_staff

router = APIRouter(tags=["Payments - Schedule"])


def _get_service(session: Session) -> PaymentScheduleService:
    uow = UnitOfWork(session)
    return PaymentScheduleService(uow)


@router.get("/students/{student_id}", response_model=List[PaymentSchedule])
def list_schedules_for_student(
    student_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> List[PaymentSchedule]:
    """
    List payment schedules for a student.
    """
    service = _get_service(session)
    # Expected: list_schedules_for_student(student_id: UUID) -> list[PaymentSchedule]
    return service.list_schedules_for_student(student_id=student_id)


@router.post("/", response_model=PaymentSchedule, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> PaymentSchedule:
    """
    Create a single payment schedule.
    """
    service = _get_service(session)
    # Expected: create_schedule(data: ScheduleCreate) -> PaymentSchedule
    return service.create_schedule(data=payload)


@router.patch("/{schedule_id}", response_model=PaymentSchedule)
def update_schedule(
    schedule_id: UUID,
    payload: ScheduleUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> PaymentSchedule:
    """
    Update an existing payment schedule.
    """
    service = _get_service(session)
    # Expected: update_schedule(schedule_id: UUID, data: ScheduleUpdate) -> PaymentSchedule
    return service.update_schedule(
        schedule_id=schedule_id,
        data=payload,
    )


@router.post("/bulk", response_model=List[PaymentSchedule], status_code=status.HTTP_201_CREATED)
def bulk_create_schedules(
    payload: BulkScheduleCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> List[PaymentSchedule]:
    """
    Bulk-create payment schedules (e.g., for all students in a hostel).
    """
    service = _get_service(session)
    # Expected: bulk_create_schedules(data: BulkScheduleCreate) -> list[PaymentSchedule]
    return service.bulk_create_schedules(data=payload)


@router.post("/{schedule_id}/generate", response_model=List[ScheduledPaymentGenerated])
def generate_payments_from_schedule(
    schedule_id: UUID,
    payload: ScheduleGeneration,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> List[ScheduledPaymentGenerated]:
    """
    Generate pending Payment records from a schedule across a Date range.
    """
    service = _get_service(session)
    # Expected:
    #   generate_payments(schedule_id: UUID, data: ScheduleGeneration)
    #     -> list[ScheduledPaymentGenerated]
    return service.generate_payments(
        schedule_id=schedule_id,
        data=payload,
    )


@router.post("/{schedule_id}/suspend", response_model=PaymentSchedule)
def suspend_schedule(
    schedule_id: UUID,
    payload: ScheduleSuspension,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> PaymentSchedule:
    """
    Suspend or resume a payment schedule.
    """
    service = _get_service(session)
    # Expected: suspend_schedule(schedule_id: UUID, data: ScheduleSuspension) -> PaymentSchedule
    return service.suspend_schedule(
        schedule_id=schedule_id,
        data=payload,
    )