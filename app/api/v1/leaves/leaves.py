from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.common.enums import LeaveStatus
from app.schemas.leave.leave_base import LeaveUpdate
from app.schemas.leave.leave_response import (
    LeaveResponse,
    LeaveDetail,
    LeaveListItem,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.leave import LeaveService

router = APIRouter()


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
    "/{leave_id}",
    response_model=LeaveDetail,
    summary="Get leave application details",
)
async def get_leave(
    leave_id: UUID = Path(..., description="Leave application ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> LeaveDetail:
    """
    Retrieve detailed information about a specific leave application.
    """
    service = LeaveService(uow)
    try:
        return service.get_leave(leave_id=leave_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/students/{student_id}",
    response_model=List[LeaveListItem],
    summary="List leaves for a student",
)
async def list_leaves_for_student(
    student_id: UUID = Path(..., description="Student ID"),
    status_filter: Union[LeaveStatus, None] = Query(
        None,
        alias="status",
        description="Optional leave status filter",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> List[LeaveListItem]:
    """
    List leave applications for a student, optionally filtered by status.
    """
    service = LeaveService(uow)
    try:
        return service.list_leaves_for_student(
            student_id=student_id,
            status=status_filter,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/pending",
    response_model=List[LeaveListItem],
    summary="List pending leave applications for a hostel",
)
async def list_pending_leaves_for_hostel(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> List[LeaveListItem]:
    """
    List all pending leave applications for a hostel (for supervisors/admins).
    """
    service = LeaveService(uow)
    try:
        return service.list_pending_for_hostel(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{leave_id}",
    response_model=LeaveDetail,
    summary="Update a leave application",
)
async def update_leave(
    leave_id: UUID = Path(..., description="Leave application ID"),
    payload: LeaveUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> LeaveDetail:
    """
    Partially update a leave application (dates, reason, contacts, document URL, etc.).

    Status changes (approve/reject) are handled via the approval endpoints.
    """
    service = LeaveService(uow)
    try:
        return service.update_leave(
            leave_id=leave_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)