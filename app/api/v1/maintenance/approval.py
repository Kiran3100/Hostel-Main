"""
Maintenance Approval API Endpoints
Handles approval/rejection of maintenance requests and threshold configuration.
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
from app.schemas.maintenance.maintenance_approval import (
    ApprovalRequest,
    ApprovalResponse,
    RejectionRequest,
    ThresholdConfig,
    ApprovalHistory,
    BulkApprovalRequest,
)
from app.services.maintenance.maintenance_approval_service import (
    MaintenanceApprovalService,
)

# Initialize router with prefix and tags
router = APIRouter(prefix="/approvals", tags=["maintenance:approval"])


def get_approval_service(
    db: Session = Depends(deps.get_db),
) -> MaintenanceApprovalService:
    """
    Dependency to get maintenance approval service instance.
    
    Args:
        db: Database session dependency
        
    Returns:
        MaintenanceApprovalService: Service instance for approval operations
    """
    return MaintenanceApprovalService(db=db)


@router.post(
    "/{request_id}/approve",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve maintenance request",
    description="Approve a pending maintenance request, allowing it to proceed to assignment",
    response_description="Approval confirmation with updated request status",
)
def approve_request(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    approval_data: Optional[ApprovalRequest] = Body(
        None,
        description="Optional approval details (notes, conditions, budget adjustments)",
    ),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    """
    Approve a maintenance request.
    
    Only admin users can approve requests. Requests requiring approval based on
    cost thresholds or priority levels must be approved before assignment.
    
    Args:
        request_id: Unique identifier of the maintenance request
        approval_data: Optional approval details and conditions
        admin: Authenticated admin user granting approval
        service: Maintenance approval service instance
        
    Returns:
        ApprovalResponse: Approval confirmation with updated request details
        
    Raises:
        HTTPException: If approval fails, request not found, or already approved/rejected
    """
    try:
        return service.approve_maintenance_request(
            request_id,
            approver_id=admin.id,
            approval_data=approval_data,
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
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve maintenance request",
        )


@router.post(
    "/{request_id}/reject",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject maintenance request",
    description="Reject a maintenance request with reason, preventing further action",
    response_description="Rejection confirmation with reason",
)
def reject_request(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    payload: RejectionRequest = Body(..., description="Rejection details including reason"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    """
    Reject a maintenance request.
    
    Rejection requires a detailed reason and prevents the request from proceeding.
    Rejected requests can be appealed or resubmitted as new requests.
    
    Args:
        request_id: Unique identifier of the maintenance request
        payload: Rejection details including mandatory reason
        admin: Authenticated admin user rejecting the request
        service: Maintenance approval service instance
        
    Returns:
        ApprovalResponse: Rejection confirmation with reason
        
    Raises:
        HTTPException: If rejection fails, request not found, or already processed
    """
    try:
        return service.reject_maintenance_request(
            request_id,
            payload,
            rejector_id=admin.id,
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
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject maintenance request",
        )


@router.post(
    "/bulk/approve",
    response_model=List[ApprovalResponse],
    summary="Bulk approve maintenance requests",
    description="Approve multiple maintenance requests in a single operation",
    response_description="List of approval confirmations",
)
def bulk_approve_requests(
    payload: BulkApprovalRequest = Body(..., description="Bulk approval details"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    """
    Approve multiple maintenance requests at once.
    
    Useful for processing routine low-cost requests in batch.
    Operation continues even if some approvals fail, returning results for each.
    
    Args:
        payload: Bulk approval details with list of request IDs
        admin: Authenticated admin user
        service: Maintenance approval service instance
        
    Returns:
        List[ApprovalResponse]: Results for each approval attempt
        
    Raises:
        HTTPException: If bulk operation fails critically
    """
    try:
        return service.bulk_approve_requests(
            payload,
            approver_id=admin.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete bulk approval",
        )


@router.get(
    "/pending",
    response_model=List[ApprovalResponse],
    summary="Get pending approval requests",
    description="Retrieve all maintenance requests awaiting approval",
    response_description="List of requests pending approval",
)
def get_pending_approvals(
    hostel_id: str = Query(..., description="Hostel ID to filter requests"),
    priority: Optional[str] = Query(
        None,
        description="Filter by priority level",
    ),
    cost_min: Optional[float] = Query(
        None,
        description="Minimum estimated cost filter",
    ),
    cost_max: Optional[float] = Query(
        None,
        description="Maximum estimated cost filter",
    ),
    pagination=Depends(deps.get_pagination_params),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    """
    Get all maintenance requests pending approval.
    
    Helps admins prioritize and process approval queue efficiently.
    
    Args:
        hostel_id: Hostel ID to filter requests
        priority: Optional priority filter
        cost_min: Minimum cost filter
        cost_max: Maximum cost filter
        pagination: Pagination parameters
        admin: Authenticated admin user
        service: Maintenance approval service instance
        
    Returns:
        List[ApprovalResponse]: Requests awaiting approval
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        return service.get_pending_approvals(
            hostel_id=hostel_id,
            priority=priority,
            cost_min=cost_min,
            cost_max=cost_max,
            pagination=pagination,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pending approvals",
        )


@router.get(
    "/history/{request_id}",
    response_model=List[ApprovalHistory],
    summary="Get approval history",
    description="Retrieve complete approval history for a maintenance request",
    response_description="Chronological approval history",
)
def get_approval_history(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    """
    Get complete approval history for a maintenance request.
    
    Shows all approval/rejection actions, appeals, and status changes.
    
    Args:
        request_id: Unique identifier of the maintenance request
        admin: Authenticated admin user
        service: Maintenance approval service instance
        
    Returns:
        List[ApprovalHistory]: Chronological approval history
        
    Raises:
        HTTPException: If request not found
    """
    try:
        return service.get_approval_history(request_id)
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve approval history",
        )


@router.get(
    "/thresholds",
    response_model=ThresholdConfig,
    summary="Get approval thresholds",
    description="Retrieve approval threshold configuration for a hostel",
    response_description="Current threshold configuration",
)
def get_threshold_config(
    hostel_id: str = Query(..., description="Hostel ID for threshold configuration"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    """
    Get approval threshold configuration for a hostel.
    
    Thresholds determine which requests require admin approval based on
    cost, priority, or other factors.
    
    Args:
        hostel_id: Hostel ID for configuration
        admin: Authenticated admin user
        service: Maintenance approval service instance
        
    Returns:
        ThresholdConfig: Current threshold configuration
        
    Raises:
        HTTPException: If configuration not found
    """
    try:
        return service.get_threshold_config_for_hostel(hostel_id)
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve threshold configuration",
        )


@router.put(
    "/thresholds",
    response_model=ThresholdConfig,
    summary="Update approval thresholds",
    description="Update approval threshold configuration for a hostel",
    response_description="Updated threshold configuration",
)
def update_threshold_config(
    payload: ThresholdConfig = Body(..., description="Updated threshold configuration"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    """
    Update approval threshold configuration.
    
    Allows admins to adjust cost limits, priority requirements, and other
    factors that trigger approval requirements.
    
    Args:
        payload: Updated threshold configuration
        admin: Authenticated admin user
        service: Maintenance approval service instance
        
    Returns:
        ThresholdConfig: Updated configuration
        
    Raises:
        HTTPException: If update fails or invalid configuration
    """
    try:
        return service.update_threshold_config(payload, actor_id=admin.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update threshold configuration",
        )


@router.post(
    "/{request_id}/appeal",
    response_model=ApprovalResponse,
    summary="Appeal rejected request",
    description="Submit an appeal for a rejected maintenance request",
    response_description="Appeal submission confirmation",
)
def appeal_rejection(
    request_id: str = Path(..., description="Unique identifier of the rejected request"),
    appeal_reason: str = Body(..., embed=True, description="Detailed reason for appeal"),
    current_user=Depends(deps.get_current_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    """
    Appeal a rejected maintenance request.
    
    Allows users to provide additional information or justification
    for reconsideration of rejected requests.
    
    Args:
        request_id: Unique identifier of the rejected request
        appeal_reason: Detailed justification for appeal
        current_user: Authenticated user submitting appeal
        service: Maintenance approval service instance
        
    Returns:
        ApprovalResponse: Appeal submission confirmation
        
    Raises:
        HTTPException: If appeal fails or request not rejected
    """
    try:
        return service.submit_appeal(
            request_id,
            appeal_reason=appeal_reason,
            appellant_id=current_user.id,
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
            detail="Failed to submit appeal",
        )