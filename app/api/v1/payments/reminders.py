# app/api/v1/payments/reminders.py
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.payment import PaymentReminderService
from app.schemas.payment.payment_reminder import (
    ReminderConfig,
    ReminderLog,
    SendReminderRequest,
    ReminderBatch,
    ReminderStats,
)
from . import CurrentUser, get_current_admin_or_staff

router = APIRouter(tags=["Payments - Reminders"])


def _get_service(session: Session) -> PaymentReminderService:
    uow = UnitOfWork(session)
    return PaymentReminderService(uow)


@router.get("/config/{hostel_id}", response_model=ReminderConfig)
def get_reminder_config(
    hostel_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> ReminderConfig:
    """
    Get reminder configuration for a hostel.
    """
    service = _get_service(session)
    # Expected: get_config(hostel_id: UUID) -> ReminderConfig
    return service.get_config(hostel_id=hostel_id)


@router.put("/config/{hostel_id}", response_model=ReminderConfig)
def update_reminder_config(
    hostel_id: UUID,
    payload: ReminderConfig,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> ReminderConfig:
    """
    Update reminder configuration for a hostel.
    """
    service = _get_service(session)
    # Expected: update_config(hostel_id: UUID, data: ReminderConfig) -> ReminderConfig
    return service.update_config(
        hostel_id=hostel_id,
        data=payload,
    )


@router.post("/send", response_model=ReminderBatch)
def send_reminders(
    payload: SendReminderRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> ReminderBatch:
    """
    Trigger sending reminders for pending/overdue payments according to config.
    """
    service = _get_service(session)
    # Expected: send_reminders(request: SendReminderRequest) -> ReminderBatch
    return service.send_reminders(request=payload)


@router.get("/logs/{hostel_id}", response_model=List[ReminderLog])
def list_reminder_logs(
    hostel_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> List[ReminderLog]:
    """
    List reminder logs for a hostel.
    """
    service = _get_service(session)
    # Expected: list_logs(hostel_id: UUID) -> list[ReminderLog]
    return service.list_logs(hostel_id=hostel_id)


@router.get("/stats/{hostel_id}", response_model=ReminderStats)
def get_reminder_stats(
    hostel_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> ReminderStats:
    """
    Get reminder statistics for a hostel.
    """
    service = _get_service(session)
    # Expected: get_stats(hostel_id: UUID) -> ReminderStats
    return service.get_stats(hostel_id=hostel_id)