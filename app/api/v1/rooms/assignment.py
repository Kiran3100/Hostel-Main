# app/api/v1/rooms/assignment.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.room import BedAssignmentService
from app.schemas.room.bed_base import (
    BedAssignmentRequest,
    BedReleaseRequest,
)
from app.schemas.room.bed_response import (
    BedAssignment,
    BedAssignmentHistory,
)
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Rooms - Bed Assignment"])


def _get_service(session: Session) -> BedAssignmentService:
    uow = UnitOfWork(session)
    return BedAssignmentService(uow)


@router.post("/", response_model=BedAssignment)
def assign_bed(
    payload: BedAssignmentRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BedAssignment:
    """
    Assign a bed to a student.

    Expected service method:
        assign_bed(data: BedAssignmentRequest) -> BedAssignment
    """
    service = _get_service(session)
    return service.assign_bed(data=payload)


@router.post("/release", response_model=BedAssignment)
def release_bed(
    payload: BedReleaseRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BedAssignment:
    """
    Release a bed from its current student.

    Expected service method:
        release_bed(data: BedReleaseRequest) -> BedAssignment
    """
    service = _get_service(session)
    return service.release_bed(data=payload)


@router.get("/history/{bed_id}", response_model=BedAssignmentHistory)
def get_bed_assignment_history(
    bed_id: str,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> BedAssignmentHistory:
    """
    Get assignment history for a bed (wrapper around StudentRoomAssignment history).

    Expected service method:
        get_bed_assignment_history(bed_id: UUID | str) -> BedAssignmentHistory
    """
    service = _get_service(session)
    return service.get_bed_assignment_history(bed_id=bed_id)