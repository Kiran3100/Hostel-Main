"""
Complaint Assignment API Endpoints
Handles assignment, reassignment, and unassignment of complaints to staff members.
"""
from typing import Any, List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.complaint import (
    AssignmentRequest,
    AssignmentResponse,
    ReassignmentRequest,
    BulkAssignment,
    BulkAssignmentResponse,
    UnassignRequest,
    AssignmentHistory,
)
from app.services.complaint.complaint_assignment_service import ComplaintAssignmentService

router = APIRouter(prefix="/complaints/assignment", tags=["complaints:assignment"])


def get_assignment_service(
    db: Session = Depends(deps.get_db),
) -> ComplaintAssignmentService:
    """
    Dependency injection for ComplaintAssignmentService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        ComplaintAssignmentService: Initialized service instance
    """
    return ComplaintAssignmentService(db=db)


@router.post(
    "/{complaint_id}",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign complaint to staff member",
    description="Assign a complaint to a staff member for resolution. Requires supervisor role.",
    responses={
        201: {"description": "Complaint assigned successfully"},
        404: {"description": "Complaint or staff member not found"},
        400: {"description": "Complaint already assigned or invalid assignment"},
        403: {"description": "Insufficient permissions"},
    },
)
def assign_complaint(
    complaint_id: str,
    payload: AssignmentRequest,
    supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Assign complaint to a staff member.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Assignment details (assignee_id, priority, deadline, notes)
        supervisor: Supervisor user making the assignment
        service: Assignment service instance
        
    Returns:
        AssignmentResponse: Assignment details with timestamps
        
    Raises:
        HTTPException: If complaint not found, already assigned, or invalid staff member
    """
    return service.assign(
        complaint_id=complaint_id,
        payload=payload,
        assigner_id=supervisor.id
    )


@router.post(
    "/{complaint_id}/reassign",
    response_model=AssignmentResponse,
    summary="Reassign complaint to different staff member",
    description="Transfer complaint assignment from one staff member to another with reason.",
    responses={
        200: {"description": "Complaint reassigned successfully"},
        404: {"description": "Complaint or new assignee not found"},
        400: {"description": "Complaint not currently assigned or invalid reassignment"},
        403: {"description": "Insufficient permissions"},
    },
)
def reassign_complaint(
    complaint_id: str,
    payload: ReassignmentRequest,
    supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Reassign complaint to a different staff member.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Reassignment details (new_assignee_id, reason, notes)
        supervisor: Supervisor user making the reassignment
        service: Assignment service instance
        
    Returns:
        AssignmentResponse: Updated assignment details
        
    Raises:
        HTTPException: If complaint not assigned or invalid reassignment
    """
    return service.reassign(
        complaint_id=complaint_id,
        payload=payload,
        assigner_id=supervisor.id
    )


@router.post(
    "/{complaint_id}/unassign",
    status_code=status.HTTP_200_OK,
    summary="Unassign complaint from staff member",
    description="Remove current assignment from a complaint. Requires reason.",
    responses={
        200: {"description": "Complaint unassigned successfully"},
        404: {"description": "Complaint not found"},
        400: {"description": "Complaint not currently assigned"},
        403: {"description": "Insufficient permissions"},
    },
)
def unassign_complaint(
    complaint_id: str,
    payload: UnassignRequest,
    supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Unassign complaint from current assignee.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Unassignment details (reason, notes)
        supervisor: Supervisor user performing the unassignment
        service: Assignment service instance
        
    Returns:
        dict: Success message
        
    Raises:
        HTTPException: If complaint not found or not assigned
    """
    service.unassign(
        complaint_id=complaint_id,
        payload=payload,
        assigner_id=supervisor.id
    )
    return {
        "success": True,
        "message": "Complaint unassigned successfully",
        "complaint_id": complaint_id
    }


@router.post(
    "/bulk",
    response_model=BulkAssignmentResponse,
    summary="Bulk assign multiple complaints",
    description="Assign multiple complaints to one or more staff members in a single operation.",
    responses={
        200: {"description": "Bulk assignment completed"},
        207: {"description": "Partial success - some assignments failed"},
        400: {"description": "Invalid bulk assignment request"},
        403: {"description": "Insufficient permissions"},
    },
)
def bulk_assign(
    payload: BulkAssignment,
    supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Bulk assign complaints to staff members.
    
    Args:
        payload: Bulk assignment data (complaint_ids, assignee_ids, distribution strategy)
        supervisor: Supervisor user performing bulk assignment
        service: Assignment service instance
        
    Returns:
        BulkAssignmentResponse: Results with successful and failed assignments
    """
    return service.bulk_assign(payload, assigner_id=supervisor.id)


@router.get(
    "/{complaint_id}/history",
    response_model=List[AssignmentHistory],
    summary="Get assignment history",
    description="Retrieve complete assignment history for a complaint including all assignments, reassignments, and unassignments.",
    responses={
        200: {"description": "Assignment history retrieved successfully"},
        404: {"description": "Complaint not found"},
    },
)
def get_assignment_history(
    complaint_id: str,
    current_user=Depends(deps.get_current_user),
    service: ComplaintAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Get complete assignment history for a complaint.
    
    Args:
        complaint_id: Unique identifier of the complaint
        current_user: Authenticated user making the request
        service: Assignment service instance
        
    Returns:
        List[AssignmentHistory]: Chronological list of assignment events
        
    Raises:
        HTTPException: If complaint not found
    """
    return service.history(complaint_id)