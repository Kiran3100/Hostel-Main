# app/api/v1/rooms/rooms.py
from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.schemas.common.enums import RoomType
from app.schemas.room.room_base import (
    RoomCreate,
    RoomUpdate,
    BulkRoomCreate,
    RoomPricingUpdate,
    RoomStatusUpdate,
)
from app.schemas.room.room_response import (
    RoomListItem,
    RoomDetail,
    RoomWithBeds,
    RoomOccupancyStats,
)
from app.services import UnitOfWork
from app.services.room import RoomService
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Rooms"])


def _get_service(session: Session) -> RoomService:
    uow = UnitOfWork(session)
    return RoomService(uow)


@router.get("/", response_model=List[RoomListItem])
def list_rooms(
    hostel_id: UUID = Query(..., description="Hostel ID to list rooms for"),
    only_available: bool = Query(
        False,
        description="If true, return only rooms available for booking",
    ),
    room_type: Union[RoomType, None] = Query(
        None,
        description="Optional filter by room type",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[RoomListItem]:
    """
    List rooms for a hostel with optional filters.

    Expected service method:
        list_rooms(hostel_id: UUID, only_available: bool, room_type: Optional[RoomType])
            -> list[RoomListItem]
    """
    service = _get_service(session)
    return service.list_rooms(
        hostel_id=hostel_id,
        only_available=only_available,
        room_type=room_type,
    )


@router.get("/{room_id}", response_model=RoomDetail)
def get_room(
    room_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> RoomDetail:
    """
    Get detailed information for a single room.

    Expected service method:
        get_room_detail(room_id: UUID) -> RoomDetail
    """
    service = _get_service(session)
    return service.get_room_detail(room_id=room_id)


@router.get("/{room_id}/with-beds", response_model=RoomWithBeds)
def get_room_with_beds(
    room_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> RoomWithBeds:
    """
    Get room details including bed information.

    Expected service method:
        get_room_with_beds(room_id: UUID) -> RoomWithBeds
    """
    service = _get_service(session)
    return service.get_room_with_beds(room_id=room_id)


@router.get("/{room_id}/occupancy", response_model=RoomOccupancyStats)
def get_room_occupancy_stats(
    room_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> RoomOccupancyStats:
    """
    Get occupancy and revenue projection stats for a room.

    Expected service method:
        get_room_occupancy_stats(room_id: UUID) -> RoomOccupancyStats
    """
    service = _get_service(session)
    return service.get_room_occupancy_stats(room_id=room_id)


@router.post(
    "/",
    response_model=RoomDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_room(
    payload: RoomCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> RoomDetail:
    """
    Create a single room.

    Expected service method:
        create_room(data: RoomCreate) -> RoomDetail
    """
    service = _get_service(session)
    return service.create_room(data=payload)


@router.post(
    "/bulk",
    response_model=List[RoomDetail],
    status_code=status.HTTP_201_CREATED,
)
def bulk_create_rooms(
    payload: BulkRoomCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[RoomDetail]:
    """
    Bulk-create rooms for a hostel.

    Expected service method:
        bulk_create_rooms(data: BulkRoomCreate) -> list[RoomDetail]
    """
    service = _get_service(session)
    return service.bulk_create_rooms(data=payload)


@router.patch("/{room_id}", response_model=RoomDetail)
def update_room(
    room_id: UUID,
    payload: RoomUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> RoomDetail:
    """
    Update room metadata and configuration.

    Expected service method:
        update_room(room_id: UUID, data: RoomUpdate) -> RoomDetail
    """
    service = _get_service(session)
    return service.update_room(
        room_id=room_id,
        data=payload,
    )


@router.patch("/{room_id}/pricing", response_model=RoomDetail)
def update_room_pricing(
    room_id: UUID,
    payload: RoomPricingUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> RoomDetail:
    """
    Update pricing for a room.

    Expected service method:
        update_room_pricing(room_id: UUID, data: RoomPricingUpdate) -> RoomDetail
    """
    service = _get_service(session)
    return service.update_room_pricing(
        room_id=room_id,
        data=payload,
    )


@router.patch("/{room_id}/status", response_model=RoomDetail)
def update_room_status(
    room_id: UUID,
    payload: RoomStatusUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> RoomDetail:
    """
    Update availability/status flags for a room.

    Expected service method:
        update_room_status(room_id: UUID, data: RoomStatusUpdate) -> RoomDetail
    """
    service = _get_service(session)
    return service.update_room_status(
        room_id=room_id,
        data=payload,
    )