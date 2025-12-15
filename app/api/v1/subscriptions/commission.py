# app/api/v1/subscriptions/commission.py
from __future__ import annotations

from datetime import date as Date 
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.subscription import CommissionService
from app.schemas.subscription.commission import (
    CommissionConfig,
    BookingCommissionResponse,
    CommissionSummary,
)
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Subscription - Commission"])


def _get_service(session: Session) -> CommissionService:
    uow = UnitOfWork(session)
    return CommissionService(uow)


@router.get("/config", response_model=CommissionConfig)
def get_commission_config(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> CommissionConfig:
    """
    Get current commission configuration.

    Expected service method:
        get_config() -> CommissionConfig
    """
    service = _get_service(session)
    return service.get_config()


@router.put("/config", response_model=CommissionConfig)
def update_commission_config(
    payload: CommissionConfig,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> CommissionConfig:
    """
    Update commission configuration.

    Expected service method:
        update_config(data: CommissionConfig) -> CommissionConfig
    """
    service = _get_service(session)
    return service.update_config(data=payload)


@router.get("/bookings/{booking_id}", response_model=BookingCommissionResponse)
def get_booking_commission(
    booking_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BookingCommissionResponse:
    """
    Get commission details for a specific booking.

    Expected service method:
        get_booking_commission(booking_id: UUID) -> BookingCommissionResponse
    """
    service = _get_service(session)
    return service.get_booking_commission(booking_id=booking_id)


@router.get("/summary", response_model=CommissionSummary)
def get_commission_summary(
    start_date: Date = Query(..., description="Start Date for the summary period"),
    end_date: Date = Query(..., description="End Date for the summary period"),
    plan_id: Optional[UUID] = Query(
        None,
        description="Optionally restrict summary to a specific subscription plan.",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> CommissionSummary:
    """
    Get commission summary for a period (optionally per plan).

    Expected service method:
        get_commission_summary(start_date: Date, end_date: Date, plan_id: Optional[UUID]) -> CommissionSummary
    """
    service = _get_service(session)
    return service.get_commission_summary(
        start_date=start_date,
        end_date=end_date,
        plan_id=plan_id,
    )