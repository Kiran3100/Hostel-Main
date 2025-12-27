"""
Maintenance Assignment API Endpoints
Handles task assignments to staff and vendors, bulk assignments, and assignment history.
"""

from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    Body,
    status,
)
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.maintenance.maintenance_assignment import (
    TaskAssignment,
    VendorAssignment,
    AssignmentUpdate,
    BulkAssignment,
    AssignmentHistory,
    AssignmentResponse,
    ReassignmentRequest,
)
from app.services.maintenance.maintenance_assignment_service import (
    MaintenanceAssignmentService,
)

# Initialize router with prefix and tags
router = APIRouter(prefix="/assignments", tags=["maintenance:assignment"])


def get_assignment_service(
    db: Session = Depends(deps.get_db),
) -> MaintenanceAssignmentService:
    """
    Dependency to get maintenance assignment service instance.
    
    Args:
        db: Database session dependency
        
    Returns:
        MaintenanceAssignmentService: Service instance for assignment operations
    """
    return MaintenanceAssignmentService(db=db)


@router.post(
    "/staff",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign task to staff",
    description="Assign a maintenance task to internal staff member",
    response_description="Created staff assignment details",
)
def assign_to_staff(
    payload: TaskAssignment = Body(..., description="Staff assignment details"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Assign a maintenance task to an internal staff member.
    
    Args:
        payload: Task assignment details including staff ID and task details
        supervisor: Authenticated supervisor user making the assignment
        service: Maintenance assignment service instance
        
    Returns:
        AssignmentResponse: Created assignment details
        
    Raises:
        HTTPException: If assignment fails or staff is unavailable
    """
    try:
        return service.assign_to_staff(payload, assigner_id=supervisor.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign task to staff",
        )


@router.post(
    "/vendor",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign task to vendor",
    description="Assign a maintenance task to an external vendor",
    response_description="Created vendor assignment details",
)
def assign_to_vendor(
    payload: VendorAssignment = Body(..., description="Vendor assignment details"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Assign a maintenance task to an external vendor.
    
    Vendor assignments typically require additional approval for high-cost tasks.
    
    Args:
        payload: Vendor assignment details including vendor ID and cost estimates
        supervisor: Authenticated supervisor user making the assignment
        service: Maintenance assignment service instance
        
    Returns:
        AssignmentResponse: Created assignment details
        
    Raises:
        HTTPException: If assignment fails, vendor is unavailable, or approval required
    """
    try:
        return service.assign_to_vendor(payload, assigner_id=supervisor.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign task to vendor",
        )


@router.put(
    "/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Update assignment details",
    description="Update details of an existing assignment (schedule, priority, notes)",
    response_description="Updated assignment details",
)
def update_assignment(
    assignment_id: str = Path(..., description="Unique identifier of the assignment"),
    payload: AssignmentUpdate = Body(..., description="Assignment update details"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Update details of an existing assignment.
    
    Allows updating scheduled time, priority, and additional notes.
    Cannot change assignee - use reassignment endpoint instead.
    
    Args:
        assignment_id: Unique identifier of the assignment
        payload: Update details
        supervisor: Authenticated supervisor user
        service: Maintenance assignment service instance
        
    Returns:
        AssignmentResponse: Updated assignment details
        
    Raises:
        HTTPException: If update fails or assignment not found
    """
    try:
        return service.update_assignment(
            assignment_id,
            payload,
            actor_id=supervisor.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update assignment",
        )


@router.post(
    "/{assignment_id}/reassign",
    response_model=AssignmentResponse,
    summary="Reassign task to different staff/vendor",
    description="Reassign an existing task to a different staff member or vendor",
    response_description="New assignment details",
)
def reassign_task(
    assignment_id: str = Path(..., description="Unique identifier of the assignment"),
    payload: ReassignmentRequest = Body(..., description="Reassignment details"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Reassign a task to a different staff member or vendor.
    
    Creates a new assignment and marks the old one as reassigned.
    Maintains history for audit purposes.
    
    Args:
        assignment_id: Unique identifier of the current assignment
        payload: Reassignment details including new assignee
        supervisor: Authenticated supervisor user
        service: Maintenance assignment service instance
        
    Returns:
        AssignmentResponse: New assignment details
        
    Raises:
        HTTPException: If reassignment fails
    """
    try:
        return service.reassign_task(
            assignment_id,
            payload,
            actor_id=supervisor.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reassign task",
        )


@router.post(
    "/bulk",
    response_model=List[AssignmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk assign tasks",
    description="Assign multiple maintenance tasks in a single operation",
    response_description="List of created assignments",
)
def bulk_assign(
    payload: BulkAssignment = Body(..., description="Bulk assignment details"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Assign multiple maintenance tasks in a single operation.
    
    Useful for assigning routine tasks or distributing workload across team.
    Operation is atomic - either all assignments succeed or none do.
    
    Args:
        payload: Bulk assignment details containing list of assignments
        supervisor: Authenticated supervisor user
        service: Maintenance assignment service instance
        
    Returns:
        List[AssignmentResponse]: List of created assignments
        
    Raises:
        HTTPException: If bulk assignment fails
    """
    try:
        return service.bulk_assign(payload, assigner_id=supervisor.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete bulk assignment",
        )


@router.get(
    "/history/{request_id}",
    response_model=List[AssignmentHistory],
    summary="Get assignment history",
    description="Retrieve complete assignment history for a maintenance request",
    response_description="List of assignment history records",
)
def get_assignment_history(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    include_cancelled: bool = Query(
        False,
        description="Include cancelled assignments in history",
    ),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Get complete assignment history for a maintenance request.
    
    Shows all assignments, reassignments, and changes over time.
    Useful for audit trails and performance analysis.
    
    Args:
        request_id: Unique identifier of the maintenance request
        include_cancelled: Whether to include cancelled assignments
        admin: Authenticated admin user
        service: Maintenance assignment service instance
        
    Returns:
        List[AssignmentHistory]: Chronological list of assignment history
        
    Raises:
        HTTPException: If request not found
    """
    try:
        return service.get_assignment_history_for_request(
            request_id,
            include_cancelled=include_cancelled,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignment history",
        )


@router.get(
    "/staff/{staff_id}",
    response_model=List[AssignmentResponse],
    summary="Get assignments for staff member",
    description="Retrieve all active assignments for a specific staff member",
    response_description="List of staff assignments",
)
def get_staff_assignments(
    staff_id: str = Path(..., description="Unique identifier of the staff member"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by assignment status",
    ),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Get all assignments for a specific staff member.
    
    Useful for workload management and task tracking.
    
    Args:
        staff_id: Unique identifier of the staff member
        status_filter: Optional status filter
        supervisor: Authenticated supervisor user
        service: Maintenance assignment service instance
        
    Returns:
        List[AssignmentResponse]: List of assignments for the staff member
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        return service.get_staff_assignments(
            staff_id,
            status_filter=status_filter,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve staff assignments",
        )


@router.get(
    "/vendor/{vendor_id}",
    response_model=List[AssignmentResponse],
    summary="Get assignments for vendor",
    description="Retrieve all active assignments for a specific vendor",
    response_description="List of vendor assignments",
)
def get_vendor_assignments(
    vendor_id: str = Path(..., description="Unique identifier of the vendor"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by assignment status",
    ),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> Any:
    """
    Get all assignments for a specific vendor.
    
    Useful for vendor management and contract tracking.
    
    Args:
        vendor_id: Unique identifier of the vendor
        status_filter: Optional status filter
        supervisor: Authenticated supervisor user
        service: Maintenance assignment service instance
        
    Returns:
        List[AssignmentResponse]: List of assignments for the vendor
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        return service.get_vendor_assignments(
            vendor_id,
            status_filter=status_filter,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vendor assignments",
        )


@router.delete(
    "/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel assignment",
    description="Cancel an assignment before work begins",
)
def cancel_assignment(
    assignment_id: str = Path(..., description="Unique identifier of the assignment"),
    reason: str = Query(..., description="Reason for cancellation"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceAssignmentService = Depends(get_assignment_service),
) -> None:
    """
    Cancel an assignment before work begins.
    
    Can only cancel assignments that haven't started yet.
    
    Args:
        assignment_id: Unique identifier of the assignment
        reason: Reason for cancellation
        supervisor: Authenticated supervisor user
        service: Maintenance assignment service instance
        
    Raises:
        HTTPException: If cancellation fails or work already started
    """
    try:
        service.cancel_assignment(
            assignment_id,
            reason=reason,
            actor_id=supervisor.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel assignment",
        )