from typing import Any, List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.booking.booking_assignment import (
    AssignmentRequest,
    AssignmentResponse,
    ReassignmentRequest,
    BulkAssignmentRequest,
    RoomAssignment,
)
from app.services.booking.booking_assignment_service import BookingAssignmentService

router = APIRouter(prefix="/bookings/assignment", tags=["bookings:assignment"])


def get_assignment_service(db: Session = Depends(deps.get_db)) -> BookingAssignmentService:
    return BookingAssignmentService(db=db)


@router.post(
    "/{booking_id}",
    response_model=AssignmentResponse,
    summary="Assign room/bed to booking",
)
def assign_room(
    booking_id: str,
    payload: AssignmentRequest,
    _admin=Depends(deps.get_admin_user),
    service: BookingAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.assign(booking_id, payload, assigner_id=_admin.id)


@router.post(
    "/{booking_id}/reassign",
    response_model=AssignmentResponse,
    summary="Reassign booking to different room/bed",
)
def reassign_room(
    booking_id: str,
    payload: ReassignmentRequest,
    _admin=Depends(deps.get_admin_user),
    service: BookingAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.reassign(booking_id, payload, assigner_id=_admin.id)


@router.post(
    "/bulk",
    response_model=List[AssignmentResponse],
    summary="Bulk assign rooms",
)
def bulk_assign(
    payload: BulkAssignmentRequest,
    _admin=Depends(deps.get_admin_user),
    service: BookingAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.bulk_assign(payload, assigner_id=_admin.id)


@router.get(
    "/{booking_id}/history",
    response_model=List[RoomAssignment],
    summary="Get assignment history",
)
def get_assignment_history(
    booking_id: str,
    _admin=Depends(deps.get_admin_user),
    service: BookingAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.get_assignment_history(booking_id)