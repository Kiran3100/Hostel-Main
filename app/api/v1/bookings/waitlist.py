# api/v1/bookings/waitlist.py

from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.booking.booking_waitlist import (
    WaitlistRequest,
    WaitlistResponse,
    WaitlistStatus,
    WaitlistNotification,
    WaitlistConversion,
    WaitlistCancellation,
    WaitlistManagement,
)
from app.schemas.common.enums import RoomType
from app.services.common.unit_of_work import UnitOfWork
from app.services.booking import BookingWaitlistService

router = APIRouter(prefix="/waitlist")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add visitor to booking waitlist",
)
async def add_to_waitlist(
    payload: WaitlistRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> WaitlistResponse:
    """
    Add a visitor to the waitlist for a hostel/room type.
    """
    service = BookingWaitlistService(uow)
    try:
        return service.add_to_waitlist(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/cancel",
    response_model=WaitlistResponse,
    summary="Cancel a waitlist entry",
)
async def cancel_waitlist_entry(
    payload: WaitlistCancellation,
    uow: UnitOfWork = Depends(get_uow),
) -> WaitlistResponse:
    """
    Cancel an existing waitlist entry.
    """
    service = BookingWaitlistService(uow)
    try:
        return service.cancel_waitlist(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/",
    response_model=WaitlistManagement,
    summary="List waitlist entries for a hostel",
)
async def list_waitlist_for_hostel(
    hostel_id: UUID = Query(..., description="Hostel ID"),
    room_type: Union[RoomType, None] = Query(None, description="Optional room type filter"),
    uow: UnitOfWork = Depends(get_uow),
) -> WaitlistManagement:
    """
    List waitlist entries for a hostel (optionally filtered by room type).
    """
    service = BookingWaitlistService(uow)
    try:
        return service.list_waitlist_for_hostel(
            hostel_id=hostel_id,
            room_type=room_type,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{entry_id}/notify",
    response_model=WaitlistResponse,
    summary="Notify a waitlist entry about availability",
)
async def notify_waitlist_entry(
    entry_id: UUID = Path(..., description="Waitlist entry ID"),
    payload: WaitlistNotification = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> WaitlistResponse:
    """
    Mark that a waitlisted visitor has been notified of availability.
    """
    service = BookingWaitlistService(uow)
    try:
        return service.notify_availability(
            entry_id=entry_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{entry_id}/convert",
    response_model=WaitlistResponse,
    summary="Convert a waitlist entry into a booking",
)
async def convert_waitlist_entry(
    entry_id: UUID = Path(..., description="Waitlist entry ID"),
    payload: WaitlistConversion = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> WaitlistResponse:
    """
    Mark a waitlist entry as converted (booking created) or declined.
    """
    service = BookingWaitlistService(uow)
    try:
        return service.mark_converted(
            entry_id=entry_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/status",
    response_model=WaitlistStatus,
    summary="Get waitlist status for a visitor",
)
async def get_waitlist_status(
    visitor_id: UUID = Query(..., description="Visitor ID"),
    hostel_id: UUID = Query(..., description="Hostel ID"),
    room_type: Union[RoomType, None] = Query(None, description="Optional room type filter"),
    uow: UnitOfWork = Depends(get_uow),
) -> WaitlistStatus:
    """
    Get current waitlist status for a visitor at a hostel (and optional room type).
    """
    service = BookingWaitlistService(uow)
    try:
        return service.get_status(
            visitor_id=visitor_id,
            hostel_id=hostel_id,
            room_type=room_type,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)