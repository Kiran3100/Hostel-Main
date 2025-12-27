from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.booking.booking_modification import (
    ModificationRequest,
    ModificationResponse,
    ModificationApproval,
)
from app.services.booking.booking_modification_service import BookingModificationService

router = APIRouter(prefix="/bookings/modification", tags=["bookings:modification"])


def get_modification_service(
    db: Session = Depends(deps.get_db),
) -> BookingModificationService:
    return BookingModificationService(db=db)


@router.post(
    "/{booking_id}/request",
    response_model=ModificationResponse,
    summary="Request booking modification",
)
def request_modification(
    booking_id: str,
    payload: ModificationRequest,
    current_user=Depends(deps.get_current_user),
    service: BookingModificationService = Depends(get_modification_service),
) -> Any:
    return service.request_modification(booking_id, payload, requester_id=current_user.id)


@router.post(
    "/requests/{request_id}/decide",
    response_model=ModificationResponse,
    summary="Approve or reject modification",
)
def decide_modification(
    request_id: str,
    payload: ModificationApproval,
    _admin=Depends(deps.get_admin_user),
    service: BookingModificationService = Depends(get_modification_service),
) -> Any:
    return service.approve_modification(request_id, payload, approver_id=_admin.id)