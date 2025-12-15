from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.leave.leave_application import (
    LeaveApplicationRequest,
    LeaveCancellationRequest,
)
from app.schemas.leave.leave_response import LeaveDetail
from app.services.common.unit_of_work import UnitOfWork
from app.services.leave import LeaveService

router = APIRouter(prefix="/apply")


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
    "/",
    response_model=LeaveDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Apply for leave",
)
async def apply_for_leave(
    payload: LeaveApplicationRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> LeaveDetail:
    """
    Submit a new leave application for a student.
    """
    service = LeaveService(uow)
    try:
        return service.apply_for_leave(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{leave_id}/cancel",
    response_model=LeaveDetail,
    summary="Cancel a leave application",
)
async def cancel_leave(
    leave_id: UUID = Path(..., description="Leave application ID"),
    payload: LeaveCancellationRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> LeaveDetail:
    """
    Request cancellation of an existing leave application.

    The service enforces that only certain statuses are cancellable.
    """
    service = LeaveService(uow)
    try:
        return service.cancel_leave(
            leave_id=leave_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)