from typing import Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
# Assuming Room schemas exist
from app.services.room.room_service import RoomService

router = APIRouter(prefix="/hostels/rooms", tags=["hostels:rooms"])


def get_room_service(db: Session = Depends(deps.get_db)) -> RoomService:
    return RoomService(db=db)


@router.get(
    "",
    summary="List rooms for a hostel",
)
def list_rooms_for_hostel(
    hostel_id: str = Query(...),
    pagination=Depends(deps.get_pagination_params),
    service: RoomService = Depends(get_room_service),
) -> Any:
    return service.list_rooms_for_hostel(hostel_id=hostel_id, pagination=pagination)