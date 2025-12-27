"""
Supervisor Assignment Management

Handles supervisor-hostel assignments including:
- Assignment creation and updates
- Assignment transfers between hostels
- Assignment revocation
- Active assignment tracking
"""

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, validator

from app.core.dependencies import AuthenticationDependency
from app.services.supervisor.supervisor_assignment_service import SupervisorAssignmentService
from app.schemas.supervisor import (
    SupervisorAssignmentCreate,
    SupervisorAssignmentUpdate,
    SupervisorAssignmentTransfer,
    SupervisorAssignment,
    SupervisorAssignmentDetail,
)

# Router configuration
router = APIRouter(
    prefix="",
    tags=["Supervisors - Assignments"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_assignment_service() -> SupervisorAssignmentService:
    """
    Dependency provider for SupervisorAssignmentService.
    
    Wire this to your DI container or service factory.
    """
    raise NotImplementedError(
        "SupervisorAssignmentService dependency must be implemented."
    )


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """Extract and validate current authenticated user."""
    user = auth.get_current_user()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user


# ============================================================================
# Request/Response Models
# ============================================================================

class AssignmentListFilters(BaseModel):
    """Filters for assignment listing"""
    status: Optional[str] = Field(None, description="Filter by status (active/inactive)")
    employment_type: Optional[str] = Field(None, description="Filter by employment type")
    start_date: Optional[datetime] = Field(None, description="Filter assignments from this date")
    end_date: Optional[datetime] = Field(None, description="Filter assignments until this date")


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/{supervisor_id}/assignments",
    response_model=SupervisorAssignmentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Assign supervisor to hostel",
    description="""
    Create a new supervisor-hostel assignment.
    
    **Assignment Details**:
    - hostel_id: Target hostel for assignment
    - employment_type: Full-time, Part-time, Contract, Temporary
    - start_date: Assignment start date
    - end_date: Optional assignment end date
    - shift_details: Shift schedule and timing
    - responsibilities: Specific duties and responsibilities
    
    **Validation**:
    - Prevents duplicate active assignments to same hostel
    - Validates supervisor availability
    - Checks hostel capacity for supervisors
    - Validates employment type compatibility
    
    **Side Effects**:
    - Updates supervisor's active assignment count
    - Triggers notification to supervisor
    - Updates hostel staffing metrics
    """,
    responses={
        201: {"description": "Assignment created successfully"},
        400: {"description": "Invalid assignment data"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor or hostel not found"},
        409: {"description": "Conflicting assignment already exists"},
    }
)
async def assign_supervisor(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    payload: SupervisorAssignmentCreate = ...,
    assignment_service: SupervisorAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorAssignmentDetail:
    """Create a new supervisor-hostel assignment."""
    result = assignment_service.assign_supervisor(
        supervisor_id=supervisor_id,
        data=payload.dict(exclude_unset=True),
        assigned_by=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        if "already assigned" in error_msg or "duplicate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.patch(
    "/assignments/{assignment_id}",
    response_model=SupervisorAssignmentDetail,
    summary="Update supervisor assignment",
    description="""
    Update an existing supervisor assignment.
    
    **Updatable Fields**:
    - employment_type: Change employment type
    - shift_details: Modify shift schedule
    - responsibilities: Update duties
    - end_date: Extend or set end date
    - status: Activate or suspend assignment
    - notes: Add administrative notes
    
    **Restrictions**:
    - Cannot change supervisor or hostel (use transfer instead)
    - Cannot update revoked assignments
    - Some changes may require approval workflow
    """,
    responses={
        200: {"description": "Assignment updated successfully"},
        400: {"description": "Invalid update data"},
        401: {"description": "Authentication required"},
        404: {"description": "Assignment not found"},
        409: {"description": "Update conflicts with business rules"},
    }
)
async def update_assignment(
    assignment_id: str = Path(..., description="Unique assignment identifier"),
    payload: SupervisorAssignmentUpdate = ...,
    assignment_service: SupervisorAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorAssignmentDetail:
    """Update assignment details."""
    result = assignment_service.update_assignment(
        assignment_id=assignment_id,
        data=payload.dict(exclude_unset=True),
        updated_by=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment with ID '{assignment_id}' not found"
            )
        if "revoked" in error_msg or "cannot update" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/assignments/{assignment_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke assignment",
    description="""
    Revoke/terminate a supervisor assignment.
    
    **Effects**:
    - Marks assignment as inactive
    - Sets revocation date and reason
    - Updates supervisor's active assignment count
    - Updates hostel staffing metrics
    - Triggers handover workflow if configured
    
    **Required Information**:
    - Revocation reason (required)
    - Revocation date (defaults to now)
    - Handover notes (optional)
    
    **Note**: Revoked assignments cannot be reactivated.
    Create a new assignment if needed.
    """,
    responses={
        204: {"description": "Assignment revoked successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Assignment not found"},
        409: {"description": "Assignment already revoked"},
    }
)
async def revoke_assignment(
    assignment_id: str = Path(..., description="Unique assignment identifier"),
    assignment_service: SupervisorAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(get_current_user),
    reason: str = Query(..., min_length=10, description="Reason for revocation"),
    effective_date: Optional[datetime] = Query(None, description="Effective revocation date"),
) -> None:
    """Revoke/terminate a supervisor assignment."""
    result = assignment_service.revoke_assignment(
        assignment_id=assignment_id,
        reason=reason,
        effective_date=effective_date.isoformat() if effective_date else None,
        revoked_by=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment with ID '{assignment_id}' not found"
            )
        if "already revoked" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Assignment is already revoked"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )


@router.post(
    "/assignments/{assignment_id}/transfer",
    response_model=SupervisorAssignmentDetail,
    summary="Transfer assignment to another hostel",
    description="""
    Transfer a supervisor assignment from one hostel to another.
    
    **Transfer Process**:
    1. Validates new hostel capacity
    2. Creates new assignment to target hostel
    3. Revokes current assignment
    4. Maintains assignment history
    5. Triggers handover workflow
    
    **Transfer Details**:
    - new_hostel_id: Target hostel ID
    - effective_date: Transfer effective date
    - reason: Transfer reason
    - preserve_settings: Keep employment type and shift details
    
    **Validation**:
    - Cannot transfer to same hostel
    - Validates new hostel availability
    - Checks supervisor transfer eligibility
    
    Returns the new assignment record.
    """,
    responses={
        200: {"description": "Assignment transferred successfully"},
        400: {"description": "Invalid transfer request"},
        401: {"description": "Authentication required"},
        404: {"description": "Assignment or target hostel not found"},
        409: {"description": "Transfer conflicts with existing assignment"},
    }
)
async def transfer_assignment(
    assignment_id: str = Path(..., description="Unique assignment identifier"),
    payload: SupervisorAssignmentTransfer = ...,
    assignment_service: SupervisorAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorAssignmentDetail:
    """Transfer assignment to a different hostel."""
    result = assignment_service.transfer_assignment(
        assignment_id=assignment_id,
        data=payload.dict(exclude_unset=True),
        transferred_by=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        if "same hostel" in error_msg or "already assigned" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{supervisor_id}/assignments",
    response_model=List[SupervisorAssignment],
    summary="List assignments for supervisor",
    description="""
    List all assignments for a specific supervisor.
    
    **Returns**:
    - All assignments (active and historical)
    - Assignment details and timeline
    - Hostel information
    - Employment details
    
    **Filtering**:
    - By status (active/inactive)
    - By date range
    - By employment type
    
    **Ordering**: Most recent assignments first
    """,
    responses={
        200: {"description": "Assignments retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def list_assignments_for_supervisor(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    assignment_service: SupervisorAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(get_current_user),
    status: Optional[str] = Query(None, regex="^(active|inactive|all)$", description="Filter by status"),
    include_revoked: bool = Query(False, description="Include revoked assignments"),
) -> List[SupervisorAssignment]:
    """List all assignments for a supervisor."""
    filters = AssignmentListFilters(status=status)
    
    result = assignment_service.list_assignments_for_supervisor(
        supervisor_id=supervisor_id,
        filters={
            **filters.dict(exclude_none=True),
            "include_revoked": include_revoked,
        },
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/hostels/{hostel_id}/assignments",
    response_model=List[SupervisorAssignment],
    summary="List supervisor assignments for hostel",
    description="""
    List all supervisor assignments for a specific hostel.
    
    **Returns**:
    - All supervisors assigned to the hostel
    - Assignment details and status
    - Supervisor information
    - Shift schedules
    
    **Use Cases**:
    - Hostel staffing overview
    - Shift planning
    - Staff directory
    
    **Ordering**: By supervisor name
    """,
    responses={
        200: {"description": "Assignments retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Hostel not found"},
    }
)
async def list_assignments_for_hostel(
    hostel_id: str = Path(..., description="Unique hostel identifier"),
    assignment_service: SupervisorAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(get_current_user),
    status: Optional[str] = Query("active", regex="^(active|inactive|all)$", description="Filter by status"),
    employment_type: Optional[str] = Query(None, description="Filter by employment type"),
) -> List[SupervisorAssignment]:
    """List all supervisor assignments for a hostel."""
    filters = {"status": status}
    if employment_type:
        filters["employment_type"] = employment_type
    
    result = assignment_service.list_assignments_for_hostel(
        hostel_id=hostel_id,
        filters=filters,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hostel with ID '{hostel_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{supervisor_id}/assignments/active",
    response_model=Optional[SupervisorAssignmentDetail],
    summary="Get active assignment for supervisor/hostel pair",
    description="""
    Get the currently active assignment for a supervisor at a specific hostel.
    
    **Returns**:
    - Active assignment details if exists
    - null if no active assignment
    
    **Use Cases**:
    - Check current assignment status
    - Validate assignment before operations
    - Get current shift details
    
    **Note**: A supervisor can have only one active assignment per hostel.
    """,
    responses={
        200: {"description": "Assignment retrieved or null if not found"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor or hostel not found"},
    }
)
async def get_active_assignment(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    assignment_service: SupervisorAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(get_current_user),
) -> Optional[SupervisorAssignmentDetail]:
    """Get active assignment for supervisor-hostel pair."""
    result = assignment_service.get_active_assignment(
        supervisor_id=supervisor_id,
        hostel_id=hostel_id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            # Return None for not found case (assignment may not exist)
            return None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/assignments/{assignment_id}",
    response_model=SupervisorAssignmentDetail,
    summary="Get assignment details",
    description="""
    Get detailed information about a specific assignment.
    
    **Includes**:
    - Complete assignment details
    - Supervisor information
    - Hostel information
    - Employment details
    - Shift schedule
    - Assignment history
    - Performance metrics
    """,
    responses={
        200: {"description": "Assignment details retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Assignment not found"},
    }
)
async def get_assignment_details(
    assignment_id: str = Path(..., description="Unique assignment identifier"),
    assignment_service: SupervisorAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorAssignmentDetail:
    """Get detailed assignment information."""
    result = assignment_service.get_assignment(assignment_id=assignment_id)
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment with ID '{assignment_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()