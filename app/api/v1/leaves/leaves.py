"""
Leave Application API Endpoints.

Handles core leave operations including:
- Application submission
- Retrieval and listing
- Cancellation
- Summary statistics

All endpoints include proper validation, error handling, and permission checks.
"""
from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.api import deps
from app.api.v1.leaves.constants import LeaveStatus, UserRole
from app.api.v1.leaves.dependencies import (
    LeaveFilterParams,
    PaginationParams,
    get_leave_application_service,
    get_leave_filter_params,
    get_pagination_params,
    get_target_student_id,
    verify_student_or_admin,
)
from app.schemas.leave.leave_application import (
    LeaveApplicationRequest,
    LeaveCancellationRequest,
)
from app.schemas.leave.leave_response import (
    LeaveDetail,
    LeaveListItem,
    LeaveResponse,
    LeaveSummary,
    PaginatedLeaveResponse,
)
from app.services.leave.leave_application_service import LeaveApplicationService

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/leaves", tags=["leaves"])


# ============================================================================
# Leave Application Endpoints
# ============================================================================

@router.post(
    "",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a leave application",
    description="""
    Submit a new leave application.
    
    **Permission**: Students only (can only apply for themselves)
    
    **Validations**:
    - Leave type must be valid
    - Date range must be valid and within policy limits
    - Student must have sufficient leave balance
    - Cannot have overlapping leave applications
    """,
    responses={
        201: {"description": "Leave application created successfully"},
        400: {"description": "Invalid request data or business rule violation"},
        403: {"description": "Permission denied"},
        409: {"description": "Conflicting leave application exists"},
    },
)
async def apply_for_leave(
    payload: LeaveApplicationRequest,
    current_student=Depends(deps.get_student_user),
    service: LeaveApplicationService = Depends(get_leave_application_service),
) -> LeaveResponse:
    """
    Submit a new leave application.
    
    Students can only apply for themselves. The student_id from the token
    is used to ensure data integrity.
    """
    # Security: Prevent students from applying on behalf of others
    if payload.student_id and payload.student_id != current_student.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot submit leave application for another student",
        )
    
    # Set student_id from authenticated user
    payload.student_id = current_student.id
    
    try:
        return service.apply(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process leave application: {str(e)}",
        )


@router.get(
    "/{leave_id}",
    response_model=LeaveDetail,
    summary="Get leave application details",
    description="""
    Retrieve detailed information about a specific leave application.
    
    **Permission**:
    - Students: Can view only their own applications
    - Admins/Wardens: Can view any application in their jurisdiction
    """,
    responses={
        200: {"description": "Leave details retrieved successfully"},
        403: {"description": "Permission denied"},
        404: {"description": "Leave application not found"},
    },
)
async def get_leave_application_detail(
    leave_id: str = Path(..., description="Unique leave application ID"),
    current_user=Depends(deps.get_current_user),
    service: LeaveApplicationService = Depends(get_leave_application_service),
) -> LeaveDetail:
    """
    Get comprehensive details of a leave application.
    
    Includes application data, approval history, and related metadata.
    """
    try:
        leave_detail = service.get_detail(leave_id, user_id=current_user.id)
        
        if not leave_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leave application with ID '{leave_id}' not found",
            )
        
        return leave_detail
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve leave details: {str(e)}",
        )


@router.post(
    "/{leave_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel a leave application",
    description="""
    Cancel a pending or approved leave application.
    
    **Permission**:
    - Students: Can cancel only their own pending applications
    - Admins: Can cancel any application
    
    **Business Rules**:
    - Only PENDING or APPROVED leaves can be cancelled
    - Cancellation reason is required
    - Past leaves cannot be cancelled
    """,
    responses={
        200: {"description": "Leave cancelled successfully"},
        400: {"description": "Cannot cancel leave (invalid status or past date)"},
        403: {"description": "Permission denied"},
        404: {"description": "Leave application not found"},
    },
)
async def cancel_leave_application(
    leave_id: str = Path(..., description="Unique leave application ID"),
    payload: LeaveCancellationRequest = ...,
    current_user=Depends(deps.get_current_user),
    service: LeaveApplicationService = Depends(get_leave_application_service),
) -> dict[str, str]:
    """
    Cancel an existing leave application.
    
    Returns a confirmation message upon successful cancellation.
    """
    try:
        service.cancel(leave_id, payload, user_id=current_user.id)
        
        return {
            "status": "success",
            "message": "Leave application cancelled successfully",
            "leave_id": leave_id,
        }
        
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel leave application: {str(e)}",
        )


# ============================================================================
# Leave Listing & Search Endpoints
# ============================================================================

@router.get(
    "",
    response_model=PaginatedLeaveResponse,
    summary="List and filter leave applications",
    description="""
    Retrieve a paginated list of leave applications with optional filters.
    
    **Permission**:
    - Students: Automatically filtered to their own applications
    - Admins/Wardens: Can filter by hostel, student, status, etc.
    
    **Filters**:
    - student_id: Filter by specific student
    - hostel_id: Filter by hostel
    - status: Filter by leave status
    - leave_type: Filter by leave type
    - date_range: Filter by date range
    """,
    responses={
        200: {"description": "Leave applications retrieved successfully"},
        400: {"description": "Invalid filter parameters"},
        403: {"description": "Permission denied"},
    },
)
async def list_leave_applications(
    filters: LeaveFilterParams = Depends(get_leave_filter_params),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user=Depends(deps.get_current_user),
    service: LeaveApplicationService = Depends(get_leave_application_service),
) -> PaginatedLeaveResponse:
    """
    List leave applications with filtering and pagination.
    
    Students automatically see only their own applications.
    Admins can filter across multiple dimensions.
    """
    try:
        # Enforce student access restrictions
        if current_user.role == UserRole.STUDENT:
            filters.student_id = current_user.id
        
        # If filtering by student
        if filters.student_id:
            results = service.list_for_student(
                student_id=filters.student_id,
                pagination=pagination.to_dict(),
                filters=filters.to_dict(),
            )
        # If filtering by hostel
        elif filters.hostel_id:
            results = service.list_for_hostel(
                hostel_id=filters.hostel_id,
                status=filters.status,
                pagination=pagination.to_dict(),
                filters=filters.to_dict(),
            )
        # Default: require context for admins
        else:
            if current_user.role != UserRole.STUDENT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please specify either student_id or hostel_id filter",
                )
            # Fallback to student's own leaves
            results = service.list_for_student(
                student_id=current_user.id,
                pagination=pagination.to_dict(),
                filters=filters.to_dict(),
            )
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve leave applications: {str(e)}",
        )


# ============================================================================
# Statistics & Summary Endpoints
# ============================================================================

@router.get(
    "/summary/statistics",
    response_model=LeaveSummary,
    summary="Get leave summary and statistics",
    description="""
    Retrieve aggregated leave statistics for a hostel.
    
    **Permission**: Admins and Wardens only
    
    **Includes**:
    - Total applications by status
    - Leave type distribution
    - Approval rates
    - Trends and patterns
    """,
    responses={
        200: {"description": "Statistics retrieved successfully"},
        400: {"description": "Invalid parameters"},
        403: {"description": "Permission denied"},
    },
)
async def get_leave_statistics(
    hostel_id: str = Query(..., description="Hostel ID for statistics"),
    _admin=Depends(deps.get_admin_user),
    service: LeaveApplicationService = Depends(get_leave_application_service),
) -> LeaveSummary:
    """
    Get comprehensive leave statistics for a hostel.
    
    Useful for administrators to monitor leave patterns and trends.
    """
    try:
        summary = service.summary(hostel_id=hostel_id)
        
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No leave data found for hostel '{hostel_id}'",
            )
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve leave statistics: {str(e)}",
        )


@router.get(
    "/my-leaves",
    response_model=List[LeaveListItem],
    summary="Get current user's leave applications",
    description="""
    Quick endpoint for students to view their own leave applications.
    
    **Permission**: Students only
    """,
)
async def get_my_leaves(
    status: Optional[str] = Query(None, description="Filter by status"),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_student=Depends(deps.get_student_user),
    service: LeaveApplicationService = Depends(get_leave_application_service),
) -> List[LeaveListItem]:
    """
    Convenience endpoint for students to view their leaves quickly.
    """
    try:
        filters = {"status": status} if status else {}
        
        return service.list_for_student(
            student_id=current_student.id,
            pagination=pagination.to_dict(),
            filters=filters,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve leaves: {str(e)}",
        )


# ============================================================================
# Bulk Operations (Admin only)
# ============================================================================

@router.post(
    "/bulk/export",
    summary="Export leave applications",
    description="Export leave applications to CSV/Excel format",
    responses={
        200: {"description": "Export successful"},
        403: {"description": "Permission denied"},
    },
)
async def export_leave_applications(
    hostel_id: str = Query(...),
    format: str = Query("csv", regex="^(csv|excel)$"),
    filters: LeaveFilterParams = Depends(get_leave_filter_params),
    _admin=Depends(deps.get_admin_user),
    service: LeaveApplicationService = Depends(get_leave_application_service),
) -> Any:
    """
    Export leave applications for reporting purposes.
    Admin only endpoint.
    """
    try:
        return service.export_leaves(
            hostel_id=hostel_id,
            format=format,
            filters=filters.to_dict(),
        )
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Export functionality coming soon",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}",
        )