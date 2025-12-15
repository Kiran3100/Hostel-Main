# app/api/v1/rooms/beds.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.room import BedService
from app.schemas.room.bed_base import (
    BedCreate,
    BedUpdate,
    BulkBedCreate,
)
from app.schemas.room.bed_response import (
    BedResponse,
    BedAvailability,
    BedHistory,
)
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Rooms - Beds"])


def _get_service(session: Session) -> BedService:
    uow = UnitOfWork(session)
    return BedService(uow)


@router.get("/{bed_id}", response_model=BedResponse)
def get_bed(
    bed_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BedResponse:
    """
    Get a single bed by ID.

    Expected service method:
        get_bed(bed_id: UUID) -> BedResponse
    """
    service = _get_service(session)
    return service.get_bed(bed_id=bed_id)


@router.get("/by-room/{room_id}", response_model=List[BedResponse])
def list_beds_for_room(
    room_id: UUID,
    only_available: bool = Query(
        False,
        description="If true, return only beds that are currently available",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[BedResponse]:
    """
    List beds for a specific room.

    Expected service method:
        list_beds_for_room(room_id: UUID, only_available: bool) -> list[BedResponse]
    """
    service = _get_service(session)
    return service.list_beds_for_room(
        room_id=room_id,
        only_available=only_available,
    )


@router.get("/{bed_id}/availability", response_model=BedAvailability)
def get_bed_availability(
    bed_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BedAvailability:
    """
    Get simple availability info for a bed.

    Expected service method:
        get_bed_availability(bed_id: UUID) -> BedAvailability
    """
    service = _get_service(session)
    return service.get_bed_availability(bed_id=bed_id)


@router.get("/{bed_id}/history", response_model=BedHistory)
def get_bed_history(
    bed_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BedHistory:
    """
    Get assignment history for a bed.

    Expected service method:
        get_bed_history(bed_id: UUID) -> BedHistory
    """
    service = _get_service(session)
    return service.get_bed_history(bed_id=bed_id)


@router.post(
    "/",
    response_model=BedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_bed(
    payload: BedCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BedResponse:
    """
    Create a single bed.

    Expected service method:
        create_bed(data: BedCreate) -> BedResponse
    """
    service = _get_service(session)
    return service.create_bed(data=payload)


@router.post(
    "/bulk",
    response_model=List[BedResponse],
    status_code=status.HTTP_201_CREATED,
)
def bulk_create_beds(
    payload: BulkBedCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[BedResponse]:
    """
    Bulk-create beds for a room.

    Expected service method:
        bulk_create_beds(data: BulkBedCreate) -> list[BedResponse]
    """
    service = _get_service(session)
    return service.bulk_create_beds(data=payload)


@router.patch("/{bed_id}", response_model=BedResponse)
def update_bed(
    bed_id: UUID,
    payload: BedUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BedResponse:
    """
    Update bed metadata or status.

    Expected service method:
        update_bed(bed_id: UUID, data: BedUpdate) -> BedResponse
    """
    service = _get_service(session)
    return service.update_bed(
        bed_id=bed_id,
        data=payload,
    )