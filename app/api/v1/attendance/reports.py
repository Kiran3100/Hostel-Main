# api/v1/attendance/reports.py

from datetime import date
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.attendance.attendance_report import (
    AttendanceReport,
    MonthlyReport,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.attendance import AttendanceReportService

router = APIRouter(prefix="/reports")


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
    "/students/{student_id}",
    response_model=AttendanceReport,
    summary="Get attendance report for a student",
)
async def get_student_attendance_report(
    student_id: UUID = Path(..., description="Student ID"),
    hostel_id: UUID = Query(..., description="Hostel ID"),
    period_start: date = Query(..., description="Start Date (inclusive)"),
    period_end: date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> AttendanceReport:
    """
    Generate a detailed attendance report for a student in a hostel over a period.
    """
    service = AttendanceReportService(uow)
    try:
        return service.get_student_report(
            student_id=student_id,
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/monthly",
    response_model=MonthlyReport,
    summary="Get monthly hostel attendance report",
)
async def get_hostel_monthly_attendance_report(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    year: int = Query(..., ge=2000, description="Year (e.g. 2025)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    uow: UnitOfWork = Depends(get_uow),
) -> MonthlyReport:
    """
    Generate a monthly attendance report for a hostel, aggregated across students.
    """
    service = AttendanceReportService(uow)
    try:
        return service.get_hostel_monthly_report(
            hostel_id=hostel_id,
            year=year,
            month=month,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)