from typing import Any, List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.booking.booking_cancellation import (
    CancellationRequest,
    CancellationResponse,
    BulkCancellation,
    CancellationPolicy,
    RefundCalculation,
)
from app.services.booking.booking_cancellation_service import BookingCancellationService

router = APIRouter(prefix="/bookings/cancellation", tags=["bookings:cancellation"])


def get_cancellation_service(
    db: Session = Depends(deps.get_db),
) -> BookingCancellationService:
    return BookingCancellationService(db=db)


@router.post(
    "/{booking_id}",
    response_model=CancellationResponse,
    summary="Cancel booking",
)
def cancel_booking(
    booking_id: str,
    payload: CancellationRequest,
    current_user=Depends(deps.get_current_user),
    service: BookingCancellationService = Depends(get_cancellation_service),
) -> Any:
    return service.cancel(booking_id, payload, actor_id=current_user.id)


@router.post(
    "/bulk",
    response_model=List[CancellationResponse],
    summary="Bulk cancel bookings",
)
def bulk_cancel(
    payload: BulkCancellation,
    _admin=Depends(deps.get_admin_user),
    service: BookingCancellationService = Depends(get_cancellation_service),
) -> Any:
    return service.bulk_cancel(payload, actor_id=_admin.id)


@router.get(
    "/{booking_id}/refund-preview",
    response_model=RefundCalculation,
    summary="Preview refund calculation",
)
def calculate_refund(
    booking_id: str,
    service: BookingCancellationService = Depends(get_cancellation_service),
) -> Any:
    return service.calculate_refund(booking_id)


@router.get(
    "/policy/{hostel_id}",
    response_model=CancellationPolicy,
    summary="Get cancellation policy",
)
def get_cancellation_policy(
    hostel_id: str,
    service: BookingCancellationService = Depends(get_cancellation_service),
) -> Any:
    return service.get_policy(hostel_id)