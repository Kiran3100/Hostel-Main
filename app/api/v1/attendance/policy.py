# api/v1/attendance/policy.py

from datetime import date
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.attendance.attendance_policy import (
    AttendancePolicy,
    PolicyUpdate,
    PolicyViolation,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.attendance import AttendancePolicyService

router = APIRouter(prefix="/policy")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.get(
    "/hostels/{hostel_id}",
    response_model=AttendancePolicy,
    summary="Get attendance policy for a hostel",
)
async def get_attendance_policy(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> AttendancePolicy:
    """
    Fetch the current attendance policy configuration for a hostel.
    """
    service = AttendancePolicyService(uow)
    try:
        return service.get_policy(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.put(
    "/hostels/{hostel_id}",
    response_model=AttendancePolicy,
    summary="Update attendance policy for a hostel",
)
async def update_attendance_policy(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    payload: PolicyUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AttendancePolicy:
    """
    Update the attendance policy for a hostel.
    """
    service = AttendancePolicyService(uow)
    try:
        return service.update_policy(
            hostel_id=hostel_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/students/{student_id}/violations",
    response_model=List[PolicyViolation],
    summary="Evaluate policy violations for a student",
)
async def get_policy_violations_for_student(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    student_id: UUID = Path(..., description="Student ID"),
    period_start: date = Query(..., description="Start Date (inclusive)"),
    period_end: date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> List[PolicyViolation]:
    """
    Evaluate attendance policy violations for a student over a given period.
    """
    service = AttendancePolicyService(uow)
    try:
        return service.evaluate_violations(
            hostel_id=hostel_id,
            student_id=student_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)