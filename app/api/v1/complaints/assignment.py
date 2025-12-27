from typing import Any, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.complaint import (
    AssignmentRequest,
    AssignmentResponse,
    ReassignmentRequest,
    BulkAssignment,
    UnassignRequest,
    AssignmentHistory,
)
from app.services.complaint.complaint_assignment_service import ComplaintAssignmentService

router = APIRouter(prefix="/complaints/assignment", tags=["complaints:assignment"])


def get_assignment_service(
    db: Session = Depends(deps.get_db),
) -> ComplaintAssignmentService:
    return ComplaintAssignmentService(db=db)


@router.post(
    "/{complaint_id}",
    response_model=AssignmentResponse,
    summary="Assign complaint to staff",
)
def assign_complaint(
    complaint_id: str,
    payload: AssignmentRequest,
    _supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.assign(
        complaint_id=complaint_id, payload=payload, assigner_id=_supervisor.id
    )


@router.post(
    "/{complaint_id}/reassign",
    response_model=AssignmentResponse,
    summary="Reassign complaint",
)
def reassign_complaint(
    complaint_id: str,
    payload: ReassignmentRequest,
    _supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.reassign(
        complaint_id=complaint_id, payload=payload, assigner_id=_supervisor.id
    )


@router.post(
    "/{complaint_id}/unassign",
    summary="Unassign complaint",
)
def unassign_complaint(
    complaint_id: str,
    payload: UnassignRequest,
    _supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintAssignmentService = Depends(get_assignment_service),
) -> Any:
    service.unassign(
        complaint_id=complaint_id, payload=payload, assigner_id=_supervisor.id
    )
    return {"detail": "Complaint unassigned"}


@router.post(
    "/bulk",
    summary="Bulk assign complaints",
)
def bulk_assign(
    payload: BulkAssignment,
    _supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.bulk_assign(payload, assigner_id=_supervisor.id)


@router.get(
    "/{complaint_id}/history",
    response_model=List[AssignmentHistory],
    summary="Get assignment history",
)
def get_assignment_history(
    complaint_id: str,
    current_user=Depends(deps.get_current_user),
    service: ComplaintAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.history(complaint_id)