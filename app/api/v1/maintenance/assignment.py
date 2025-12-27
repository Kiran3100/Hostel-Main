from typing import Any, List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.maintenance.maintenance_assignment import (
    TaskAssignment,
    VendorAssignment,
    AssignmentUpdate,
    BulkAssignment,
    AssignmentHistory,
)
from app.services.maintenance.maintenance_assignment_service import MaintenanceAssignmentService

router = APIRouter(prefix="/assignments", tags=["maintenance:assignment"])


def get_assignment_service(
    db: Session = Depends(deps.get_db),
) -> MaintenanceAssignmentService:
    return MaintenanceAssignmentService(db=db)


@router.post(
    "/staff",
    response_model=TaskAssignment,
    summary="Assign task to staff",
)
def assign_to_staff(
    payload: TaskAssignment,
    _supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.assign_to_staff(payload, assigner_id=_supervisor.id)


@router.post(
    "/vendor",
    response_model=VendorAssignment,
    summary="Assign task to vendor",
)
def assign_to_vendor(
    payload: VendorAssignment,
    _supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.assign_to_vendor(payload, assigner_id=_supervisor.id)


@router.put(
    "/{assignment_id}",
    summary="Update assignment details",
)
def update_assignment(
    assignment_id: str,
    payload: AssignmentUpdate,
    _supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.update_assignment(assignment_id, payload, actor_id=_supervisor.id)


@router.post(
    "/bulk",
    summary="Bulk assign tasks",
)
def bulk_assign(
    payload: BulkAssignment,
    _supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.bulk_assign(payload, assigner_id=_supervisor.id)


@router.get(
    "/history/{request_id}",
    response_model=List[AssignmentHistory],
    summary="Get assignment history",
)
def get_assignment_history(
    request_id: str,
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.get_assignment_history_for_request(request_id)