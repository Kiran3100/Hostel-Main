"""
Leave Approval API Endpoints.

Handles leave approval workflow including:
- Approve/Reject decisions
- Workflow actions (escalate, delegate)
- Pending approvals queue
- Approval history tracking

All endpoints enforce role-based access control.
"""
from typing import Any, List

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
from app.api.v1.leaves.constants import WorkflowAction
from app.api.v1.leaves.dependencies import (
    PaginationParams,
    get_leave_approval_service,
    get_pagination_params,
    verify_approver_role,
)
from app.schemas.leave.leave_approval import (
    LeaveApprovalAction,
    LeaveApprovalRequest,
    LeaveApprovalResponse,
    LeaveApprovalHistoryResponse,
    PendingApprovalItem,
)
from app.services.leave.leave_approval_service import LeaveApprovalService

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/leaves/approval", tags=["leaves:approval"])


# ============================================================================
# Approval Decision Endpoints
# ============================================================================

@router.post(
    "/{leave_id}/decide",
    response_model=LeaveApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve or reject a leave application",
    description="""
    Make an approval decision on a pending leave application.
    
    **Permission**: Wardens, Supervisors, and Admins only
    
    **Actions**:
    - APPROVE: Grant the leave application
    - REJECT: Deny the leave application
    
    **Requirements**:
    - Leave must be in PENDING or ESCALATED status
    - Comments required for rejection
    - Approver must have jurisdiction over the hostel
    """,
    responses={
        200: {"description": "Decision recorded successfully"},
        400: {"description": "Invalid decision or leave state"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Leave application not found"},
        409: {"description": "Leave already processed"},
    },
)
async def make_approval_decision(
    leave_id: str = Path(..., description="Unique leave application ID"),
    payload: LeaveApprovalRequest = ...,
    current_approver=Depends(verify_approver_role),
    service: LeaveApprovalService = Depends(get_leave_approval_service),
) -> LeaveApprovalResponse:
    """
    Process an approval or rejection decision for a leave application.
    
    The decision is logged with timestamp, approver details, and comments.
    Notifications are sent to relevant parties.
    """
    try:
        # Validate payload
        if not payload.decision:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Decision (approve/reject) is required",
            )
        
        # Reject requires comments
        if payload.decision.lower() == "reject" and not payload.comments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Comments are required when rejecting a leave application",
            )
        
        # Process the decision
        result = service.decide(
            leave_id=leave_id,
            payload=payload,
            approver_id=current_approver.id,
        )
        
        return result
        
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
            detail=f"Failed to process approval decision: {str(e)}",
        )


# ============================================================================
# Workflow Action Endpoints
# ============================================================================

@router.post(
    "/{leave_id}/workflow",
    status_code=status.HTTP_200_OK,
    summary="Execute workflow action on leave application",
    description="""
    Perform advanced workflow actions on a leave application.
    
    **Permission**: Wardens, Supervisors, and Admins
    
    **Actions**:
    - ESCALATE: Forward to higher authority for decision
    - DELEGATE: Assign to another approver
    
    **Use Cases**:
    - Escalation: Complex cases requiring senior approval
    - Delegation: Temporary reassignment during absence
    """,
    responses={
        200: {"description": "Workflow action completed"},
        400: {"description": "Invalid action or parameters"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Leave application not found"},
    },
)
async def execute_workflow_action(
    leave_id: str = Path(..., description="Unique leave application ID"),
    payload: LeaveApprovalAction = ...,
    current_user=Depends(verify_approver_role),
    service: LeaveApprovalService = Depends(get_leave_approval_service),
) -> dict[str, Any]:
    """
    Execute workflow actions like escalation or delegation.
    
    Maintains complete audit trail of all workflow transitions.
    """
    try:
        # Validate action type
        valid_actions = {e.value for e in WorkflowAction}
        if payload.action not in valid_actions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action. Must be one of: {', '.join(valid_actions)}",
            )
        
        # Delegate requires target user
        if payload.action == WorkflowAction.DELEGATE and not payload.target_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_user_id is required for delegation",
            )
        
        # Execute the workflow action
        result = service.workflow_action(
            leave_id=leave_id,
            payload=payload,
            actor_id=current_user.id,
        )
        
        return {
            "status": "success",
            "message": f"Workflow action '{payload.action}' completed successfully",
            "leave_id": leave_id,
            "action": payload.action,
            "result": result,
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
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute workflow action: {str(e)}",
        )


# ============================================================================
# Pending Approvals Endpoints
# ============================================================================

@router.get(
    "/pending",
    response_model=List[PendingApprovalItem],
    summary="Get pending approvals for current user",
    description="""
    Retrieve all leave applications pending approval by the current user.
    
    **Permission**: Wardens, Supervisors, and Admins
    
    **Returns**: List of applications awaiting decision, sorted by priority/date
    
    **Use Case**: Dashboard view for approvers to manage their queue
    """,
    responses={
        200: {"description": "Pending approvals retrieved successfully"},
        403: {"description": "Insufficient permissions"},
    },
)
async def get_pending_approvals(
    priority: str = Query(
        "all",
        regex="^(all|high|normal|low)$",
        description="Filter by priority level",
    ),
    hostel_id: str = Query(None, description="Filter by specific hostel"),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_approver=Depends(verify_approver_role),
    service: LeaveApprovalService = Depends(get_leave_approval_service),
) -> List[PendingApprovalItem]:
    """
    Get all leave applications pending approval by the current user.
    
    Results are ordered by urgency and submission date.
    """
    try:
        pending_items = service.get_pending_approvals(
            approver_id=current_approver.id,
            hostel_id=hostel_id,
            priority=priority if priority != "all" else None,
            pagination=pagination.to_dict(),
        )
        
        return pending_items
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve pending approvals: {str(e)}",
        )


@router.get(
    "/pending/count",
    summary="Get count of pending approvals",
    description="Quick count of pending approvals for dashboard badges",
)
async def get_pending_count(
    current_approver=Depends(verify_approver_role),
    service: LeaveApprovalService = Depends(get_leave_approval_service),
) -> dict[str, int]:
    """
    Get count of pending approvals for the current approver.
    Useful for dashboard notifications and badges.
    """
    try:
        count = service.get_pending_count(approver_id=current_approver.id)
        
        return {
            "pending_count": count,
            "approver_id": current_approver.id,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending count: {str(e)}",
        )


# ============================================================================
# Approval History Endpoints
# ============================================================================

@router.get(
    "/{leave_id}/history",
    response_model=LeaveApprovalHistoryResponse,
    summary="Get complete approval history for a leave application",
    description="""
    Retrieve the complete approval history and audit trail.
    
    **Permission**: 
    - Students: Can view history of their own applications
    - Approvers: Can view history of applications in their jurisdiction
    
    **Includes**:
    - All approval/rejection actions
    - Workflow transitions (escalations, delegations)
    - Timestamps and actor information
    - Comments and reasons
    """,
    responses={
        200: {"description": "History retrieved successfully"},
        403: {"description": "Permission denied"},
        404: {"description": "Leave application not found"},
    },
)
async def get_approval_history(
    leave_id: str = Path(..., description="Unique leave application ID"),
    current_user=Depends(deps.get_current_user),
    service: LeaveApprovalService = Depends(get_leave_approval_service),
) -> LeaveApprovalHistoryResponse:
    """
    Get comprehensive approval history with full audit trail.
    
    Useful for transparency and dispute resolution.
    """
    try:
        history = service.get_history(
            leave_id=leave_id,
            requesting_user_id=current_user.id,
        )
        
        if not history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No approval history found for leave ID '{leave_id}'",
            )
        
        return history
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve approval history: {str(e)}",
        )


# ============================================================================
# Bulk Approval Operations (Admin)
# ============================================================================

@router.post(
    "/bulk/approve",
    summary="Bulk approve multiple leave applications",
    description="Admin endpoint for bulk approval of leave applications",
    responses={
        200: {"description": "Bulk approval completed"},
        400: {"description": "Invalid request"},
        403: {"description": "Permission denied"},
    },
)
async def bulk_approve_leaves(
    leave_ids: List[str] = Query(..., description="List of leave IDs to approve"),
    comments: str = Query(None, description="Common approval comments"),
    _admin=Depends(deps.get_admin_user),
    service: LeaveApprovalService = Depends(get_leave_approval_service),
) -> dict[str, Any]:
    """
    Approve multiple leave applications in one operation.
    Admin only for efficiency during mass approvals.
    """
    try:
        if not leave_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one leave_id is required",
            )
        
        if len(leave_ids) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 leaves can be approved at once",
            )
        
        results = service.bulk_approve(
            leave_ids=leave_ids,
            approver_id=_admin.id,
            comments=comments,
        )
        
        return {
            "status": "success",
            "total": len(leave_ids),
            "approved": results.get("approved", 0),
            "failed": results.get("failed", 0),
            "details": results.get("details", []),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk approval failed: {str(e)}",
        )


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get(
    "/analytics/approval-rate",
    summary="Get approval rate analytics",
    description="Get approval statistics and trends",
)
async def get_approval_analytics(
    hostel_id: str = Query(...),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    _admin=Depends(deps.get_admin_user),
    service: LeaveApprovalService = Depends(get_leave_approval_service),
) -> dict[str, Any]:
    """
    Get approval rate analytics for monitoring and reporting.
    """
    try:
        analytics = service.get_approval_analytics(
            hostel_id=hostel_id,
            days=days,
        )
        
        return analytics
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve analytics: {str(e)}",
        )