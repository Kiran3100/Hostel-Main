from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.booking.booking_base import (
    BookingCreate,
    BookingUpdate,
)
from app.schemas.booking.booking_response import (
    BookingDetail,
    BookingListItem,
    BookingResponse,
)
from app.services.booking.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["bookings"])


def get_booking_service(db: Session = Depends(deps.get_db)) -> BookingService:
    return BookingService(db=db)


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new booking",
)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(deps.get_db),
    # If this is public/visitor-facing, authentication might be optional or visitor-based
    # If admin-facing, require admin user. Adjust accordingly.
    current_user=Depends(deps.get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> Any:
    return service.create_booking(payload, creator_id=current_user.id)


@router.get(
    "/{booking_id}",
    response_model=BookingDetail,
    summary="Get booking details",
)
def get_booking(
    booking_id: str,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> Any:
    booking = service.get_detail(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


@router.put(
    "/{booking_id}",
    response_model=BookingDetail,
    summary="Update booking",
)
def update_booking(
    booking_id: str,
    payload: BookingUpdate,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> Any:
    return service.update_booking(booking_id, payload, updater_id=current_user.id)


@router.get(
    "",
    response_model=List[BookingListItem],
    summary="List bookings",
)
def list_bookings(
    pagination=Depends(deps.get_pagination_params),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> Any:
    return service.list_bookings(pagination=pagination)