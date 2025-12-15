# api/v1/attendance/record.py

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.attendance.attendance_record import (
    AttendanceRecordRequest,
    BulkAttendanceRequest,
    AttendanceCorrection,
    QuickAttendanceMarkAll,
)
from app.schemas.attendance.attendance_response import AttendanceDetail
from app.schemas.common.response import BulkOperationResponse
from app.services.common.unit_of_work import UnitOfWork
from app.services.attendance import AttendanceService

router = APIRouter(prefix="/mark")


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


@router.post(
    "/single",
    response_model=AttendanceDetail,
    status_code=status.HTTP_200_OK,
    summary="Mark attendance for a single student",
)
async def mark_single_attendance(
    payload: AttendanceRecordRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> AttendanceDetail:
    """
    Mark attendance for a single student on a given day.
    """
    service = AttendanceService(uow)
    try:
        return service.mark_attendance(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bulk",
    response_model=BulkOperationResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk mark attendance",
)
async def bulk_mark_attendance(
    payload: BulkAttendanceRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> BulkOperationResponse:
    """
    Bulk mark attendance for many students in one call.
    """
    service = AttendanceService(uow)
    try:
        return service.bulk_mark_attendance(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/correction",
    response_model=AttendanceDetail,
    status_code=status.HTTP_200_OK,
    summary="Correct an existing attendance record",
)
async def correct_attendance(
    payload: AttendanceCorrection,
    uow: UnitOfWork = Depends(get_uow),
) -> AttendanceDetail:
    """
    Apply a correction to an existing attendance record (status/time updates, etc.).
    """
    service = AttendanceService(uow)
    try:
        return service.correct_attendance(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/mark-all",
    response_model=BulkOperationResponse,
    status_code=status.HTTP_200_OK,
    summary="Quick mark all present with exceptions",
)
async def quick_mark_all(
    payload: QuickAttendanceMarkAll,
    uow: UnitOfWork = Depends(get_uow),
) -> BulkOperationResponse:
    """
    Quickly mark all students present, with specific exceptions (absent/late/etc.).
    """
    service = AttendanceService(uow)
    try:
        return service.quick_mark_all(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)