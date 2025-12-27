from typing import Any, List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.booking.booking_waitlist import (
    WaitlistRequest,
    WaitlistResponse,
    WaitlistEntry,
    WaitlistConversion,
    WaitlistCancellation,
)
from app.services.booking.booking_waitlist_service import BookingWaitlistService

router = APIRouter(prefix="/bookings/waitlist", tags=["bookings:waitlist"])


def get_waitlist_service(db: Session = Depends(deps.get_db)) -> BookingWaitlistService:
    return BookingWaitlistService(db=db)


@router.post(
    "",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Join waitlist",
)
def join_waitlist(
    payload: WaitlistRequest,
    current_user=Depends(deps.get_current_user),
    service: BookingWaitlistService = Depends(get_waitlist_service),
) -> Any:
    return service.join(payload, user_id=current_user.id)


@router.post(
    "/{entry_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel waitlist entry",
)
def cancel_waitlist(
    entry_id: str,
    payload: WaitlistCancellation,
    current_user=Depends(deps.get_current_user),
    service: BookingWaitlistService = Depends(get_waitlist_service),
) -> Any:
    service.cancel(entry_id, payload, actor_id=current_user.id)
    return {"detail": "Waitlist entry cancelled"}


@router.post(
    "/{entry_id}/convert",
    response_model=Any,  # Likely returns BookingResponse
    summary="Convert waitlist to booking",
)
def convert_waitlist(
    entry_id: str,
    payload: WaitlistConversion,
    current_user=Depends(deps.get_current_user),
    service: BookingWaitlistService = Depends(get_waitlist_service),
) -> Any:
    return service.convert_to_booking(entry_id, payload, user_id=current_user.id)


@router.get(
    "",
    response_model=List[WaitlistEntry],
    summary="List my waitlist entries",
)
def get_my_waitlist(
    current_user=Depends(deps.get_current_user),
    service: BookingWaitlistService = Depends(get_waitlist_service),
) -> Any:
    return service.get_user_waitlist_entries(user_id=current_user.id)