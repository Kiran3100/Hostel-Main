# api/v1/leaves/approval.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.leave.leave_approval import (
    LeaveApprovalRequest,
    LeaveApprovalResponse,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.leave import LeaveApprovalService

router = APIRouter(prefix="/approval")


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
    "/{leave_id}",
    response_model=LeaveApprovalResponse,
    summary="Approve or reject a leave application",
)
async def approve_or_reject_leave(
    leave_id: UUID = Path(..., description="Leave application ID"),
    payload: LeaveApprovalRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> LeaveApprovalResponse:
    """
    Supervisor/admin approval or rejection of a leave application.

    Only pending leaves can be approved/rejected.
    """
    service = LeaveApprovalService(uow)
    try:
        return service.process_approval(
            leave_id=leave_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)