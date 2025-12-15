# app/api/v1/admin/assignments.py

from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.admin.admin_hostel_assignment import (
    AdminHostelAssignment,
    AssignmentCreate,
    AssignmentUpdate,
    BulkAssignment,
    RevokeAssignment,
    AssignmentList,
    HostelAdminList,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.admin import AdminHostelAssignmentService

router = APIRouter(prefix="/assignments")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# -------- Admin → Hostels -------- #


@router.get(
    "/admins/{admin_id}",
    response_model=AssignmentList,
    summary="List hostel assignments for an admin",
)
async def list_admin_assignments(
    admin_id: UUID = Path(..., description="Admin ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> AssignmentList:
    """
    Return all hostel assignments for a given admin, including primary flags and permissions.
    """
    service = AdminHostelAssignmentService(uow)
    try:
        return service.list_assignments_for_admin(admin_id=admin_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/admins/{admin_id}",
    response_model=AdminHostelAssignment,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an admin to a hostel",
)
async def create_admin_assignment(
    admin_id: UUID,
    payload: AssignmentCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> AdminHostelAssignment:
    """
    Create a single admin↔hostel assignment.

    Enforces:
    - Uniqueness per (admin, hostel)
    - At most one primary hostel per admin
    """
    service = AdminHostelAssignmentService(uow)
    try:
        return service.create_assignment(admin_id=admin_id, data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/admins/{admin_id}/{assignment_id}",
    response_model=AdminHostelAssignment,
    summary="Update admin↔hostel assignment",
)
async def update_admin_assignment(
    admin_id: UUID,
    assignment_id: UUID,
    payload: AssignmentUpdate,
    uow: UnitOfWork = Depends(get_uow),
) -> AdminHostelAssignment:
    """
    Update assignment metadata (permissions, primary flag, etc.).
    """
    service = AdminHostelAssignmentService(uow)
    try:
        return service.update_assignment(
            admin_id=admin_id,
            assignment_id=assignment_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/admins/{admin_id}/bulk",
    response_model=List[AdminHostelAssignment],
    summary="Bulk assign admin to multiple hostels",
)
async def bulk_assign_admin(
    admin_id: UUID,
    payload: BulkAssignment,
    uow: UnitOfWork = Depends(get_uow),
) -> List[AdminHostelAssignment]:
    """
    Bulk-assign an admin to multiple hostels in one call.
    """
    service = AdminHostelAssignmentService(uow)
    try:
        return service.bulk_assign(admin_id=admin_id, data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/admins/{admin_id}/{assignment_id}/revoke",
    response_model=AdminHostelAssignment,
    summary="Revoke admin↔hostel assignment",
)
async def revoke_admin_assignment(
    admin_id: UUID,
    assignment_id: UUID,
    payload: RevokeAssignment,
    uow: UnitOfWork = Depends(get_uow),
) -> AdminHostelAssignment:
    """
    Revoke an assignment with a reason; typically marks it inactive and records revoked_date.
    """
    service = AdminHostelAssignmentService(uow)
    try:
        return service.revoke_assignment(
            admin_id=admin_id,
            assignment_id=assignment_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


# -------- Hostel → Admins -------- #


@router.get(
    "/hostels/{hostel_id}",
    response_model=HostelAdminList,
    summary="List admins for a hostel",
)
async def list_hostel_admins(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> HostelAdminList:
    """
    List all admins assigned to a given hostel, with metadata.
    """
    service = AdminHostelAssignmentService(uow)
    try:
        return service.list_admins_for_hostel(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)