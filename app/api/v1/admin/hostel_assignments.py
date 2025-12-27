from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.admin import (
    AdminHostelAssignment,
    AssignmentCreate,
    AssignmentUpdate,
    BulkAssignment,
    RevokeAssignment,
    AssignmentList,
    HostelAdminList,
)
from app.services.admin.hostel_assignment_service import HostelAssignmentService

router = APIRouter(prefix="/hostel-assignments", tags=["admin:hostel-assignments"])


def get_hostel_assignment_service(
    db: Session = Depends(deps.get_db),
) -> HostelAssignmentService:
    return HostelAssignmentService(db=db)


@router.post(
    "",
    response_model=AdminHostelAssignment,
    status_code=status.HTTP_201_CREATED,
    summary="Assign admin to hostel",
)
def create_assignment(
    payload: AssignmentCreate,
    _super_admin=Depends(deps.get_super_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> Any:
    return service.create_assignment(payload)


@router.get(
    "",
    response_model=AssignmentList,
    summary="List assignments for current admin or all (super-admin)",
)
def list_assignments(
    admin_id: Optional[str] = Query(None, description="Filter by admin ID"),
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    current_admin=Depends(deps.get_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> Any:
    """
    If admin_id is not provided, returns assignments for the current admin.
    Super-admins can query for any combination.
    """
    target_admin_id = admin_id or current_admin.id
    return service.get_admin_assignments(admin_id=target_admin_id, hostel_id=hostel_id)


@router.get(
    "/hostel/{hostel_id}",
    response_model=HostelAdminList,
    summary="List all admins assigned to a hostel",
)
def list_hostel_admins(
    hostel_id: str,
    _admin=Depends(deps.get_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> Any:
    return service.get_hostel_assignments(hostel_id=hostel_id)


@router.put(
    "/{assignment_id}",
    response_model=AdminHostelAssignment,
    summary="Update assignment",
)
def update_assignment(
    assignment_id: str,
    payload: AssignmentUpdate,
    _super_admin=Depends(deps.get_super_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> Any:
    return service.update_assignment(assignment_id=assignment_id, payload=payload)


@router.post(
    "/bulk",
    response_model=AssignmentList,
    summary="Bulk assign one admin to multiple hostels",
)
def bulk_assign(
    payload: BulkAssignment,
    _super_admin=Depends(deps.get_super_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> Any:
    return service.bulk_assign(payload)


@router.post(
    "/{assignment_id}/revoke",
    status_code=status.HTTP_200_OK,
    summary="Revoke admin-hostel assignment",
)
def revoke_assignment(
    assignment_id: str,
    payload: RevokeAssignment,
    _super_admin=Depends(deps.get_super_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> Any:
    return service.revoke_assignment(assignment_id=assignment_id, payload=payload)


@router.post(
    "/{assignment_id}/primary",
    response_model=AdminHostelAssignment,
    summary="Set primary hostel for admin",
)
def set_primary_hostel(
    assignment_id: str,
    _super_admin=Depends(deps.get_super_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> Any:
    return service.set_primary_hostel(assignment_id=assignment_id)