# api/v1/leaves/balance.py
from __future__ import annotations

from datetime import date as Date

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.leave.leave_balance import LeaveBalanceSummary
from app.services.common.unit_of_work import UnitOfWork
from app.services.leave import LeaveBalanceService

router = APIRouter(prefix="/balance")


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
    response_model=LeaveBalanceSummary,
    summary="Get leave balance summary for a student",
)
async def get_leave_balance_summary(
    student_id: UUID = Path(..., description="Student ID"),
    hostel_id: UUID = Query(..., description="Hostel ID"),
    academic_year_start: Date = Query(
        ...,
        description="Start Date of the academic year (inclusive)",
    ),
    academic_year_end: Date = Query(
        ...,
        description="End Date of the academic year (inclusive)",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> LeaveBalanceSummary:
    """
    Return leave balance summary per type for a student within an academic year.
    """
    service = LeaveBalanceService(uow)
    try:
        return service.get_balance_summary(
            student_id=student_id,
            hostel_id=hostel_id,
            academic_year_start=academic_year_start,
            academic_year_end=academic_year_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)