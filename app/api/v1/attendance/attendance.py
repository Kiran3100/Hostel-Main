# api/v1/attendance/attendance.py

from datetime import date
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.attendance.attendance_base import AttendanceCreate, AttendanceUpdate
from app.schemas.attendance.attendance_response import (
    AttendanceResponse,
    AttendanceDetail,
    DailyAttendanceSummary,
)
from app.schemas.attendance.attendance_filters import AttendanceFilterParams
from app.services.common.unit_of_work import UnitOfWork
from app.services.attendance import AttendanceService

router = APIRouter(prefix="/records")


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
    "/",
    response_model=List[AttendanceResponse],
    summary="List attendance records",
)
async def list_attendance_records(
    filters: AttendanceFilterParams = Depends(),
    uow: UnitOfWork = Depends(get_uow),
) -> List[AttendanceResponse]:
    """
    List attendance records using filters (hostel, student, date range, status, mode, etc.).
    """
    service = AttendanceService(uow)
    try:
        return service.list_attendance(filters=filters)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/",
    response_model=AttendanceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create an attendance record",
)
async def create_attendance_record(
    payload: AttendanceCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> AttendanceDetail:
    """
    Create a single attendance record.
    """
    service = AttendanceService(uow)
    try:
        return service.create_attendance(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{attendance_id}",
    response_model=AttendanceDetail,
    summary="Get attendance record details",
)
async def get_attendance_record(
    attendance_id: UUID = Path(..., description="Attendance record ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> AttendanceDetail:
    """
    Retrieve full details for a specific attendance record.
    """
    service = AttendanceService(uow)
    try:
        return service.get_attendance(attendance_id=attendance_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{attendance_id}",
    response_model=AttendanceDetail,
    summary="Update an attendance record",
)
async def update_attendance_record(
    attendance_id: UUID = Path(..., description="Attendance record ID"),
    payload: AttendanceUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AttendanceDetail:
    """
    Partially update an attendance record (times, status, notes, etc.).
    """
    service = AttendanceService(uow)
    try:
        return service.update_attendance(
            attendance_id=attendance_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/summary",
    response_model=DailyAttendanceSummary,
    summary="Get daily attendance summary for a hostel",
)
async def get_daily_hostel_summary(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    day: date = Query(..., description="Date for the summary (YYYY-MM-DD)"),
    uow: UnitOfWork = Depends(get_uow),
) -> DailyAttendanceSummary:
    """
    Get summarized attendance statistics for a hostel on a specific day.
    """
    service = AttendanceService(uow)
    try:
        return service.get_daily_summary(
            hostel_id=hostel_id,
            day=day,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)