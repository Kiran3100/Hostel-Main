"""
Maintenance Requests API Endpoints
Handles creation, retrieval, listing, and status updates for maintenance requests.
"""

from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
    Path,
    Body,
)
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.maintenance.maintenance_base import (
    MaintenanceCreate,
    MaintenanceUpdate,
    MaintenanceStatusUpdate,
)
from app.schemas.maintenance.maintenance_request import (
    MaintenanceRequest,
    EmergencyRequest,
)
from app.schemas.maintenance.maintenance_response import (
    MaintenanceDetail,
    MaintenanceListItem,
    MaintenanceResponse,
)
from app.services.maintenance.maintenance_request_service import (
    MaintenanceRequestService,
)

# Initialize router with prefix and tags
router = APIRouter(prefix="/requests", tags=["maintenance:requests"])


def get_request_service(
    db: Session = Depends(deps.get_db),
) -> MaintenanceRequestService:
    """
    Dependency to get maintenance request service instance.
    
    Args:
        db: Database session dependency
        
    Returns:
        MaintenanceRequestService: Service instance for maintenance operations
    """
    return MaintenanceRequestService(db=db)


@router.post(
    "",
    response_model=MaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create maintenance request (resident)",
    description="Allows residents to create a new maintenance request for their room or common areas",
    response_description="Created maintenance request details",
)
def create_request(
    payload: MaintenanceCreate = Body(..., description="Maintenance request details"),
    current_user=Depends(deps.get_current_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    """
    Create a new maintenance request as a resident.
    
    Args:
        payload: Maintenance request creation data
        current_user: Authenticated user making the request
        service: Maintenance request service instance
        
    Returns:
        MaintenanceResponse: Created maintenance request
        
    Raises:
        HTTPException: If request creation fails
    """
    try:
        return service.create_resident_request(payload, creator_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create maintenance request",
        )


@router.post(
    "/supervisor",
    response_model=MaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create maintenance request (supervisor)",
    description="Allows supervisors to create maintenance requests on behalf of residents or for proactive maintenance",
    response_description="Created maintenance request details",
)
def create_supervisor_request(
    payload: MaintenanceCreate = Body(..., description="Maintenance request details"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    """
    Create a new maintenance request as a supervisor.
    
    Supervisors can create requests for proactive maintenance or on behalf of residents.
    
    Args:
        payload: Maintenance request creation data
        supervisor: Authenticated supervisor user
        service: Maintenance request service instance
        
    Returns:
        MaintenanceResponse: Created maintenance request
        
    Raises:
        HTTPException: If request creation fails
    """
    try:
        return service.create_supervisor_submission(payload, creator_id=supervisor.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create supervisor maintenance request",
        )


@router.post(
    "/emergency",
    response_model=MaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create emergency maintenance request",
    description="Creates a high-priority emergency maintenance request requiring immediate attention",
    response_description="Created emergency maintenance request",
)
def create_emergency_request(
    payload: EmergencyRequest = Body(..., description="Emergency request details"),
    current_user=Depends(deps.get_current_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    """
    Create an emergency maintenance request.
    
    Emergency requests are given highest priority and trigger immediate notifications.
    
    Args:
        payload: Emergency request creation data
        current_user: Authenticated user creating the emergency request
        service: Maintenance request service instance
        
    Returns:
        MaintenanceResponse: Created emergency maintenance request
        
    Raises:
        HTTPException: If emergency request creation fails
    """
    try:
        return service.create_emergency_request(payload, creator_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create emergency maintenance request",
        )


@router.get(
    "/{request_id}",
    response_model=MaintenanceDetail,
    summary="Get request details",
    description="Retrieve detailed information about a specific maintenance request",
    response_description="Detailed maintenance request information",
    responses={
        404: {"description": "Request not found"},
        403: {"description": "Not authorized to view this request"},
    },
)
def get_request(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    current_user=Depends(deps.get_current_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    """
    Get detailed information about a maintenance request.
    
    Args:
        request_id: Unique identifier of the maintenance request
        current_user: Authenticated user requesting the details
        service: Maintenance request service instance
        
    Returns:
        MaintenanceDetail: Detailed maintenance request information
        
    Raises:
        HTTPException: 404 if request not found, 403 if unauthorized
    """
    request = service.get_request(request_id)
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance request with ID {request_id} not found",
        )
    
    # Additional authorization check could be added here
    # to ensure user has permission to view this request
    
    return request


@router.get(
    "",
    response_model=List[MaintenanceListItem],
    summary="List maintenance requests",
    description="Retrieve a paginated list of maintenance requests with optional filtering by status",
    response_description="List of maintenance requests",
)
def list_requests(
    hostel_id: str = Query(..., description="Hostel ID to filter requests"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by request status (pending, approved, in_progress, completed, rejected)",
    ),
    priority: Optional[str] = Query(
        None,
        description="Filter by priority level (low, medium, high, emergency)",
    ),
    pagination=Depends(deps.get_pagination_params),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    """
    List maintenance requests with filtering and pagination.
    
    Admin users can view all requests for a hostel with optional filtering.
    
    Args:
        hostel_id: Hostel ID to filter requests
        status_filter: Optional status filter
        priority: Optional priority filter
        pagination: Pagination parameters (skip, limit)
        admin: Authenticated admin user
        service: Maintenance request service instance
        
    Returns:
        List[MaintenanceListItem]: Paginated list of maintenance requests
        
    Raises:
        HTTPException: If listing fails
    """
    try:
        if status_filter:
            return service.get_requests_by_status(
                hostel_id=hostel_id,
                status=status_filter,
                pagination=pagination,
            )
        
        return service.list_requests_for_hostel(
            hostel_id=hostel_id,
            pagination=pagination,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve maintenance requests",
        )


@router.patch(
    "/{request_id}/status",
    response_model=MaintenanceResponse,
    summary="Update request status",
    description="Update the status of a maintenance request (requires supervisor privileges)",
    response_description="Updated maintenance request",
    responses={
        404: {"description": "Request not found"},
        400: {"description": "Invalid status transition"},
    },
)
def update_status(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    payload: MaintenanceStatusUpdate = Body(..., description="Status update details"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    """
    Update the status of a maintenance request.
    
    Only supervisors can update request status. Valid transitions are enforced
    by the service layer.
    
    Args:
        request_id: Unique identifier of the maintenance request
        payload: Status update information
        supervisor: Authenticated supervisor user
        service: Maintenance request service instance
        
    Returns:
        MaintenanceResponse: Updated maintenance request
        
    Raises:
        HTTPException: If update fails or invalid status transition
    """
    try:
        return service.update_status(request_id, payload, actor_id=supervisor.id)
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
            detail="Failed to update maintenance request status",
        )


@router.put(
    "/{request_id}",
    response_model=MaintenanceResponse,
    summary="Update maintenance request",
    description="Update maintenance request details (only before assignment)",
    response_description="Updated maintenance request",
)
def update_request(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    payload: MaintenanceUpdate = Body(..., description="Update details"),
    current_user=Depends(deps.get_current_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    """
    Update maintenance request details.
    
    Users can only update their own requests and only before assignment.
    
    Args:
        request_id: Unique identifier of the maintenance request
        payload: Update information
        current_user: Authenticated user
        service: Maintenance request service instance
        
    Returns:
        MaintenanceResponse: Updated maintenance request
        
    Raises:
        HTTPException: If update fails or not allowed
    """
    try:
        return service.update_request(request_id, payload, actor_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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
            detail="Failed to update maintenance request",
        )


@router.delete(
    "/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel maintenance request",
    description="Cancel a pending maintenance request (only before assignment)",
)
def cancel_request(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    current_user=Depends(deps.get_current_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> None:
    """
    Cancel a pending maintenance request.
    
    Users can only cancel their own pending requests before assignment.
    
    Args:
        request_id: Unique identifier of the maintenance request
        current_user: Authenticated user
        service: Maintenance request service instance
        
    Raises:
        HTTPException: If cancellation fails or not allowed
    """
    try:
        service.cancel_request(request_id, actor_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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
            detail="Failed to cancel maintenance request",
        )