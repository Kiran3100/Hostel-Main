# api/v1/bookings/assignment.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.booking.booking_assignment import (
    AssignmentRequest,
    BulkAssignmentRequest,
    ReassignmentRequest,
    AssignmentResponse,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.booking import BookingService

router = APIRouter(prefix="/assignments")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{booking_id}",
    response_model=AssignmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign room/bed for a booking",
)
async def assign_booking(
    booking_id: UUID = Path(..., description="Booking ID"),
    payload: AssignmentRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AssignmentResponse:
    """
    Assign a room and optionally a bed to a booking.
    """
    service = BookingService(uow)
    try:
        return service.assign_booking(
            booking_id=booking_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bulk",
    response_model=List[AssignmentResponse],
    summary="Bulk assign rooms/beds for bookings",
)
async def bulk_assign_bookings(
    payload: BulkAssignmentRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> List[AssignmentResponse]:
    """
    Bulk assign rooms/beds to multiple bookings.
    """
    service = BookingService(uow)
    try:
        return service.bulk_assign_bookings(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{booking_id}/reassign",
    response_model=AssignmentResponse,
    summary="Reassign room/bed for a booking",
)
async def reassign_booking(
    booking_id: UUID = Path(..., description="Booking ID"),
    payload: ReassignmentRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AssignmentResponse:
    """
    Reassign a booking to a new room/bed.
    """
    service = BookingService(uow)
    try:
        return service.reassign_booking(
            booking_id=booking_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)