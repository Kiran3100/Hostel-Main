# app/api/v1/rooms/availability.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.room import RoomAvailabilityService
from app.schemas.room.room_availability import (
    RoomAvailabilityRequest,
    AvailabilityResponse,
)

router = APIRouter(tags=["Rooms - Availability"])


def _get_service(session: Session) -> RoomAvailabilityService:
    uow = UnitOfWork(session)
    return RoomAvailabilityService(uow)


@router.post("/", response_model=AvailabilityResponse)
def get_room_availability(
    payload: RoomAvailabilityRequest,
    session: Session = Depends(get_session),
) -> AvailabilityResponse:
    """
    Compute room availability for a hostel/Date/room_type combination.

    Expected service method:
        get_availability(request: RoomAvailabilityRequest) -> AvailabilityResponse
    """
    service = _get_service(session)
    return service.get_availability(request=payload)