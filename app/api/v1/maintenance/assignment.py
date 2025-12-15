# api/v1/maintenance/assignment.py
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.maintenance.maintenance_assignment import (
    TaskAssignment,
    VendorAssignment,
    AssignmentUpdate,
    BulkAssignment,
    AssignmentHistory,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.maintenance import MaintenanceAssignmentService

router = APIRouter(prefix="/assignment")


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
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{maintenance_id}",
    response_model=TaskAssignment,
    status_code=status.HTTP_200_OK,
    summary="Assign maintenance request to a supervisor/staff",
)
async def assign_maintenance(
    maintenance_id: UUID = Path(..., description="Maintenance request ID"),
    payload: TaskAssignment = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> TaskAssignment:
    """
    Assign a maintenance request to a supervisor or staff member.
    """
    service = MaintenanceAssignmentService(uow)
    try:
        return service.assign_task(
            maintenance_id=maintenance_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{maintenance_id}/vendor",
    response_model=TaskAssignment,
    summary="Assign maintenance request to a vendor",
)
async def assign_vendor(
    maintenance_id: UUID = Path(..., description="Maintenance request ID"),
    payload: VendorAssignment = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> TaskAssignment:
    """
    Assign or update vendor information for a maintenance request.
    """
    service = MaintenanceAssignmentService(uow)
    try:
        return service.assign_vendor(
            maintenance_id=maintenance_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{maintenance_id}",
    response_model=TaskAssignment,
    summary="Update maintenance assignment",
)
async def update_maintenance_assignment(
    maintenance_id: UUID = Path(..., description="Maintenance request ID"),
    payload: AssignmentUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> TaskAssignment:
    """
    Update an existing assignment (e.g. reassignment, deadline, instructions).
    """
    service = MaintenanceAssignmentService(uow)
    try:
        return service.update_assignment(
            maintenance_id=maintenance_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bulk",
    response_model=List[TaskAssignment],
    summary="Bulk assign maintenance requests",
)
async def bulk_assign_maintenance(
    payload: BulkAssignment,
    uow: UnitOfWork = Depends(get_uow),
) -> List[TaskAssignment]:
    """
    Bulk assign multiple maintenance requests to supervisors/staff.
    """
    service = MaintenanceAssignmentService(uow)
    try:
        return service.bulk_assign(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{maintenance_id}/history",
    response_model=AssignmentHistory,
    summary="Get assignment history for a maintenance request",
)
async def get_assignment_history(
    maintenance_id: UUID = Path(..., description="Maintenance request ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> AssignmentHistory:
    """
    Retrieve the full assignment history for a maintenance request.
    """
    service = MaintenanceAssignmentService(uow)
    try:
        return service.get_history(maintenance_id=maintenance_id)
    except ServiceError as exc:
        raise _map_service_error(exc)