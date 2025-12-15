# api/v1/attendance/bulk.py

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.attendance.attendance_base import BulkAttendanceCreate
from app.schemas.common.response import BulkOperationResponse
from app.services.common.unit_of_work import UnitOfWork
from app.services.attendance import AttendanceService

router = APIRouter(prefix="/bulk")


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
    "/create",
    response_model=BulkOperationResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk create attendance records",
)
async def bulk_create_attendance(
    payload: BulkAttendanceCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> BulkOperationResponse:
    """
    Bulk-create attendance records from a structured list of records.
    """
    service = AttendanceService(uow)
    try:
        return service.bulk_create_attendance(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)