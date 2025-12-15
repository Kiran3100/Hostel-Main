# api/v1/complaints/assignment.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.complaint.complaint_assignment import (
    AssignmentRequest,
    AssignmentResponse,
    ReassignmentRequest,
    BulkAssignment,
    UnassignRequest,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.complaint import ComplaintAssignmentService

router = APIRouter(prefix="/assignments")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.post(
    "/{complaint_id}",
    response_model=AssignmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign a complaint to a supervisor",
)
async def assign_complaint(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: AssignmentRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AssignmentResponse:
    """
    Assign a complaint to a supervisor (or staff member).
    """
    service = ComplaintAssignmentService(uow)
    try:
        return service.assign_complaint(
            complaint_id=complaint_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{complaint_id}/reassign",
    response_model=AssignmentResponse,
    summary="Reassign a complaint",
)
async def reassign_complaint(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: ReassignmentRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AssignmentResponse:
    """
    Reassign a complaint to a different supervisor.
    """
    service = ComplaintAssignmentService(uow)
    try:
        return service.reassign_complaint(
            complaint_id=complaint_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bulk",
    response_model=List[AssignmentResponse],
    summary="Bulk assign complaints",
)
async def bulk_assign_complaints(
    payload: BulkAssignment,
    uow: UnitOfWork = Depends(get_uow),
) -> List[AssignmentResponse]:
    """
    Bulk assign multiple complaints to supervisors.
    """
    service = ComplaintAssignmentService(uow)
    try:
        return service.bulk_assign(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{complaint_id}/unassign",
    response_model=AssignmentResponse,
    summary="Unassign a complaint",
)
async def unassign_complaint(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: UnassignRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AssignmentResponse:
    """
    Remove the current supervisor assignment from a complaint.
    """
    service = ComplaintAssignmentService(uow)
    try:
        return service.unassign_complaint(
            complaint_id=complaint_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)