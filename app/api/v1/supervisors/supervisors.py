"""
Supervisor Core CRUD Operations

Handles supervisor creation, retrieval, updates, and listing with filtering.
Provides comprehensive supervisor profile management and counting operations.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.core.dependencies import AuthenticationDependency
from app.services.supervisor.supervisor_service import SupervisorService
from app.schemas.supervisor import (
    SupervisorCreate,
    SupervisorUpdate,
    SupervisorResponse,
    SupervisorDetail,
    SupervisorListItem,
    SupervisorSummary,
)

# Router configuration
router = APIRouter(
    prefix="",  # No prefix here since parent router has /supervisors
    tags=["Supervisors - Core"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_supervisor_service() -> SupervisorService:
    """
    Dependency provider for SupervisorService.
    
    This should be implemented to return a properly configured service instance.
    Example implementation using dependency injection container:
    
    from app.core.container import get_container
    return get_container().supervisor_service()
    """
    raise NotImplementedError(
        "SupervisorService dependency must be implemented. "
        "Wire this to your DI container or service factory."
    )


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Extract and validate current authenticated user.
    
    Returns:
        Current user object with authentication context
        
    Raises:
        HTTPException: If authentication fails
    """
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

class SupervisorListFilters(BaseModel):
    """Filters for supervisor listing endpoint"""
    hostel_id: Optional[str] = Field(None, description="Filter by hostel ID")
    status: Optional[str] = Field(None, description="Filter by supervisor status")
    search: Optional[str] = Field(None, description="Search term for name, email, phone")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


class SupervisorCountResponse(BaseModel):
    """Response model for supervisor count"""
    total: int = Field(..., description="Total number of supervisors")
    active: Optional[int] = Field(None, description="Number of active supervisors")
    inactive: Optional[int] = Field(None, description="Number of inactive supervisors")
    by_hostel: Optional[Dict[str, int]] = Field(None, description="Count by hostel")


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "",
    response_model=SupervisorDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create new supervisor",
    description="""
    Create a new supervisor in the system.
    
    **Admin Operation**: Requires administrative privileges.
    
    - Creates supervisor profile with employment details
    - Optionally assigns to initial hostel
    - Sets up default permissions
    - Initializes activity tracking
    
    **Request Body**:
    - personal_info: Name, contact details, identification
    - employment_info: Employment type, hire date, salary details
    - hostel_assignment: Optional initial hostel assignment
    """,
    responses={
        201: {"description": "Supervisor created successfully"},
        400: {"description": "Invalid request data"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Supervisor already exists"},
    }
)
async def create_supervisor(
    payload: SupervisorCreate,
    supervisor_service: SupervisorService = Depends(get_supervisor_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorDetail:
    """Create a new supervisor with full profile and optional initial assignment."""
    result = supervisor_service.create_supervisor(data=payload.dict(exclude_unset=True))
    
    if result.is_err():
        error = result.unwrap_err()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "",
    response_model=List[SupervisorListItem],
    summary="List supervisors",
    description="""
    Retrieve paginated list of supervisors with optional filtering.
    
    **Filtering Options**:
    - hostel_id: Filter by assigned hostel
    - status: Filter by active/inactive status
    - search: Search by name, email, or phone number
    
    **Pagination**:
    - Default page size: 20
    - Maximum page size: 100
    
    Returns lightweight supervisor list items optimized for listing views.
    """,
    responses={
        200: {"description": "List retrieved successfully"},
        401: {"description": "Authentication required"},
    }
)
async def list_supervisors(
    supervisor_service: SupervisorService = Depends(get_supervisor_service),
    current_user: Any = Depends(get_current_user),
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    status: Optional[str] = Query(None, description="Filter by status (active/inactive)"),
    search: Optional[str] = Query(None, min_length=2, description="Search term (min 2 characters)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> List[SupervisorListItem]:
    """List supervisors with filtering and pagination."""
    filters = SupervisorListFilters(
        hostel_id=hostel_id,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )
    
    result = supervisor_service.list_supervisors(filters=filters.dict(exclude_none=True))
    
    if result.is_err():
        error = result.unwrap_err()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/count",
    response_model=SupervisorCountResponse,
    summary="Get supervisor count",
    description="""
    Get total count of supervisors with optional breakdowns.
    
    **Returns**:
    - Total supervisor count
    - Count by status (active/inactive)
    - Count by hostel assignment
    
    Useful for dashboard statistics and reporting.
    """,
    responses={
        200: {"description": "Count retrieved successfully"},
        401: {"description": "Authentication required"},
    }
)
async def get_supervisor_count(
    supervisor_service: SupervisorService = Depends(get_supervisor_service),
    current_user: Any = Depends(get_current_user),
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
) -> SupervisorCountResponse:
    """Get total count of supervisors with optional filtering."""
    filters = {}
    if hostel_id:
        filters["hostel_id"] = hostel_id
    if status:
        filters["status"] = status
    
    result = supervisor_service.get_supervisor_count(filters=filters)
    
    if result.is_err():
        error = result.unwrap_err()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return SupervisorCountResponse(**result.unwrap())


@router.get(
    "/{supervisor_id}",
    response_model=SupervisorDetail,
    summary="Get supervisor details",
    description="""
    Retrieve complete supervisor details by ID.
    
    **Includes**:
    - Personal information
    - Employment details
    - Current hostel assignments
    - Permission summary
    - Recent activity summary
    - Performance metrics overview
    
    Returns comprehensive supervisor profile data.
    """,
    responses={
        200: {"description": "Supervisor details retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_supervisor(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    supervisor_service: SupervisorService = Depends(get_supervisor_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorDetail:
    """Retrieve full supervisor details including all related data."""
    result = supervisor_service.get_supervisor(supervisor_id=supervisor_id)
    
    if result.is_err():
        error = result.unwrap_err()
        # Check if it's a not found error
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
    "/{supervisor_id}/profile",
    response_model=SupervisorDetail,
    summary="Get supervisor profile",
    description="""
    Retrieve supervisor's extended profile information.
    
    Similar to get_supervisor but may include additional profile-specific data:
    - Education and certifications
    - Training history
    - Emergency contacts
    - Documents and attachments
    
    Use this endpoint for profile management screens.
    """,
    responses={
        200: {"description": "Profile retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_supervisor_profile(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    supervisor_service: SupervisorService = Depends(get_supervisor_service),
    current_user: Any = Depends(get_current_user),
    include_sensitive: bool = Query(False, description="Include sensitive data (requires elevated permissions)"),
) -> SupervisorDetail:
    """Retrieve extended supervisor profile with optional sensitive data."""
    result = supervisor_service.get_supervisor_profile(
        supervisor_id=supervisor_id,
        include_sensitive=include_sensitive
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        if "permission" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to access sensitive data"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.patch(
    "/{supervisor_id}",
    response_model=SupervisorDetail,
    summary="Update supervisor",
    description="""
    Partially update supervisor information.
    
    **Updatable Fields**:
    - Personal information (contact details, address)
    - Employment details (status, position, salary)
    - Administrative notes
    - Metadata and custom fields
    
    Only provided fields will be updated. Omitted fields remain unchanged.
    
    **Note**: Some fields may require elevated permissions to modify.
    """,
    responses={
        200: {"description": "Supervisor updated successfully"},
        400: {"description": "Invalid update data"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Supervisor not found"},
    }
)
async def update_supervisor(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    payload: SupervisorUpdate = ...,
    supervisor_service: SupervisorService = Depends(get_supervisor_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorDetail:
    """Update supervisor information with partial data."""
    result = supervisor_service.update_supervisor(
        supervisor_id=supervisor_id,
        data=payload.dict(exclude_unset=True),
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        if "permission" in error_msg or "forbidden" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update supervisor"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.delete(
    "/{supervisor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete supervisor",
    description="""
    Soft delete a supervisor from the system.
    
    **Admin Operation**: Requires administrative privileges.
    
    - Marks supervisor as inactive
    - Revokes all active assignments
    - Preserves historical data for audit trail
    - Cannot be undone without database access
    
    **Warning**: This is a destructive operation.
    """,
    responses={
        204: {"description": "Supervisor deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Supervisor not found"},
        409: {"description": "Cannot delete supervisor with active assignments"},
    }
)
async def delete_supervisor(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    supervisor_service: SupervisorService = Depends(get_supervisor_service),
    current_user: Any = Depends(get_current_user),
    force: bool = Query(False, description="Force delete even with active assignments"),
) -> None:
    """Soft delete supervisor and revoke assignments."""
    result = supervisor_service.delete_supervisor(
        supervisor_id=supervisor_id,
        force=force
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        if "active assignment" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete supervisor with active assignments. Use force=true to override."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )


@router.post(
    "/{supervisor_id}/reactivate",
    response_model=SupervisorDetail,
    summary="Reactivate supervisor",
    description="""
    Reactivate a previously deactivated supervisor.
    
    **Admin Operation**: Requires administrative privileges.
    
    - Restores supervisor to active status
    - Does not automatically restore previous assignments
    - Resets login credentials if needed
    """,
    responses={
        200: {"description": "Supervisor reactivated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Supervisor not found"},
    }
)
async def reactivate_supervisor(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    supervisor_service: SupervisorService = Depends(get_supervisor_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorDetail:
    """Reactivate a deactivated supervisor."""
    result = supervisor_service.reactivate_supervisor(supervisor_id=supervisor_id)
    
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