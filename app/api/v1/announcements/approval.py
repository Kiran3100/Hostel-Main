"""
Enhanced announcement approval workflow with improved state management.
"""
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger, log_endpoint_call
from app.core.security import require_permissions
from app.schemas.announcement import (
    ApprovalRequest,
    ApprovalResponse,
    RejectionRequest,
    ApprovalWorkflow,
    SupervisorApprovalQueue,
    BulkApproval,
    ApprovalHistory,
)
from app.services.announcement.announcement_approval_service import AnnouncementApprovalService
from .deps import get_approval_service

logger = get_logger(__name__)
router = APIRouter(
    prefix="/announcements/approval",
    tags=["announcements:approval"],
    responses={
        404: {"description": "Approval request not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Invalid state transition"}
    }
)


# ---------------------------------------------------------------------------
# Approval Request Lifecycle
# ---------------------------------------------------------------------------

@router.post(
    "/submit",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit announcement for approval",
    description="""
    Submit an announcement for supervisor/admin approval.
    
    **Workflow stages:**
    1. Content validation and completeness check
    2. Automatic policy compliance screening
    3. Queue assignment based on content type and urgency
    4. Notification dispatch to relevant approvers
    
    **Required for approval:**
    - Complete announcement content
    - Target audience configuration
    - Valid priority level
    - Compliance with content policies
    """,
    response_description="Approval request details and tracking information"
)
@require_permissions(["announcement:submit_approval"])
@log_endpoint_call
async def submit_for_approval(
    payload: ApprovalRequest,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> ApprovalResponse:
    """
    Submit announcement for approval with comprehensive validation.
    """
    try:
        logger.info(
            f"Submitting announcement for approval",
            extra={
                "actor_id": current_user.id,
                "announcement_id": getattr(payload, 'announcement_id', None),
                "priority": getattr(payload, 'priority', 'normal')
            }
        )
        
        result = await service.submit_for_approval(
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.info(
            f"Successfully submitted approval request",
            extra={
                "actor_id": current_user.id,
                "approval_id": result.id,
                "announcement_id": result.announcement_id
            }
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid approval submission: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Approval submission failed: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Submission failed")


@router.post(
    "/{approval_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve announcement",
    description="""
    Approve a pending announcement for publication.
    
    **Approval authority:**
    - Content supervisors: General announcements
    - Admin staff: Policy and emergency announcements
    - System admin: All announcement types
    
    **Auto-actions on approval:**
    - Notification to submitter
    - Publication scheduling (if configured)
    - Audit trail creation
    - Metrics tracking initiation
    """,
    responses={
        200: {"description": "Announcement approved successfully"},
        409: {"description": "Already processed or invalid state"}
    }
)
@require_permissions(["announcement:approve"])
@log_endpoint_call
async def approve_announcement(
    approval_id: UUID,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> ApprovalResponse:
    """
    Approve announcement with authority validation and auto-actions.
    """
    try:
        logger.info(
            f"Approving announcement request {approval_id}",
            extra={"actor_id": current_user.id, "approval_id": str(approval_id)}
        )
        
        result = await service.approve(
            approval_id=str(approval_id),
            actor_id=current_user.id,
        )
        
        logger.info(
            f"Successfully approved announcement",
            extra={
                "actor_id": current_user.id,
                "approval_id": str(approval_id),
                "announcement_id": result.announcement_id
            }
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid approval action: {str(e)}", extra={"approval_id": str(approval_id)})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for approval", extra={"actor_id": current_user.id, "approval_id": str(approval_id)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient approval authority")
    except Exception as e:
        logger.error(f"Approval failed: {str(e)}", extra={"approval_id": str(approval_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Approval processing failed")


@router.post(
    "/{approval_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject announcement",
    description="""
    Reject a pending announcement with detailed feedback.
    
    **Rejection handling:**
    - Mandatory reason and feedback
    - Automatic submitter notification
    - Revision suggestions (optional)
    - Re-submission pathway guidance
    
    **Common rejection reasons:**
    - Content policy violation
    - Insufficient information
    - Inappropriate targeting
    - Timing conflicts
    - Technical issues
    """,
    responses={
        200: {"description": "Announcement rejected with feedback"},
        409: {"description": "Already processed or invalid state"}
    }
)
@require_permissions(["announcement:reject"])
@log_endpoint_call
async def reject_announcement(
    approval_id: UUID,
    payload: RejectionRequest,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> ApprovalResponse:
    """
    Reject announcement with comprehensive feedback and guidance.
    """
    try:
        logger.warning(
            f"Rejecting announcement request {approval_id}",
            extra={
                "actor_id": current_user.id,
                "approval_id": str(approval_id),
                "reason": getattr(payload, 'reason', 'Not specified')
            }
        )
        
        result = await service.reject(
            approval_id=str(approval_id),
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.warning(
            f"Successfully rejected announcement",
            extra={
                "actor_id": current_user.id,
                "approval_id": str(approval_id),
                "announcement_id": result.announcement_id
            }
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid rejection: {str(e)}", extra={"approval_id": str(approval_id)})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Rejection failed: {str(e)}", extra={"approval_id": str(approval_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Rejection processing failed")


# ---------------------------------------------------------------------------
# Bulk Operations and Queue Management
# ---------------------------------------------------------------------------

@router.post(
    "/bulk-decide",
    response_model=List[ApprovalResponse],
    summary="Bulk approve/reject announcements",
    description="""
    Process multiple approval requests in a single operation.
    
    **Bulk processing features:**
    - Atomic transaction handling
    - Individual decision tracking
    - Partial success reporting
    - Comprehensive audit logging
    
    **Limitations:**
    - Maximum 50 requests per bulk operation
    - All requests must be in pending state
    - Requires elevated admin privileges
    """,
    responses={
        200: {"description": "All decisions processed successfully"},
        207: {"description": "Partial success with detailed results"}
    }
)
@require_permissions(["announcement:bulk_approve"])
@log_endpoint_call
async def bulk_decide(
    payload: BulkApproval,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> List[ApprovalResponse]:
    """
    Process bulk approval/rejection decisions with detailed result tracking.
    """
    try:
        approval_ids = getattr(payload, 'approval_ids', [])
        logger.info(
            f"Processing bulk approval decisions",
            extra={
                "actor_id": current_user.id,
                "request_count": len(approval_ids),
                "decision_type": getattr(payload, 'decision', 'unknown')
            }
        )
        
        results = await service.bulk_decide(
            payload=payload,
            actor_id=current_user.id,
        )
        
        success_count = len([r for r in results if r.status in ['approved', 'rejected']])
        logger.info(
            f"Bulk decisions processed",
            extra={
                "actor_id": current_user.id,
                "total_requests": len(approval_ids),
                "successful": success_count,
                "failed": len(approval_ids) - success_count
            }
        )
        
        # Return 207 Multi-Status if there were any failures
        if success_count < len(approval_ids):
            return JSONResponse(
                status_code=status.HTTP_207_MULTI_STATUS,
                content=[r.model_dump() for r in results]
            )
        
        return results
        
    except ValueError as e:
        logger.warning(f"Invalid bulk decision request: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Bulk decision processing failed: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Bulk processing failed")


# ---------------------------------------------------------------------------
# Workflow Information and History
# ---------------------------------------------------------------------------

@router.get(
    "/workflows/{announcement_id}",
    response_model=ApprovalWorkflow,
    summary="Get approval workflow for announcement",
    description="""
    Retrieve complete approval workflow information for an announcement.
    
    **Workflow details include:**
    - Current approval state and stage
    - Required approvers and their status
    - Historical approval actions
    - Estimated approval timeline
    - Escalation pathways if applicable
    """,
    response_description="Complete workflow state and progression details"
)
@log_endpoint_call
async def get_approval_workflow(
    announcement_id: UUID,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> ApprovalWorkflow:
    """
    Get comprehensive approval workflow information with access control.
    """
    try:
        result = await service.get_workflow(
            announcement_id=str(announcement_id),
            actor_id=current_user.id,
        )
        
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Workflow retrieval failed: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Workflow retrieval failed")


@router.get(
    "/queue",
    response_model=SupervisorApprovalQueue,
    summary="Get supervisor's approval queue",
    description="""
    Retrieve pending approval requests assigned to the current supervisor.
    
    **Queue organization:**
    - Priority-based sorting (urgent first)
    - Age-based secondary sorting
    - Content type grouping
    - Workload balancing indicators
    
    **Queue metrics:**
    - Total pending requests
    - Average processing time
    - Overdue request alerts
    - Capacity recommendations
    """,
    response_description="Prioritized queue with processing metrics"
)
@require_permissions(["announcement:supervise"])
@log_endpoint_call
async def get_supervisor_queue(
    include_metrics: bool = Query(True, description="Include queue performance metrics"),
    current_user=Depends(deps.get_supervisor_user),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> SupervisorApprovalQueue:
    """
    Get prioritized approval queue with optional performance metrics.
    """
    try:
        result = await service.get_supervisor_queue(
            supervisor_id=current_user.id,
            include_metrics=include_metrics,
        )
        
        logger.debug(
            f"Retrieved supervisor queue",
            extra={
                "supervisor_id": current_user.id,
                "pending_count": len(getattr(result, 'pending_requests', []))
            }
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Queue retrieval failed: {str(e)}", extra={"supervisor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Queue retrieval failed")


@router.get(
    "/history/{announcement_id}",
    response_model=ApprovalHistory,
    summary="Get approval history for announcement",
    description="""
    Retrieve complete approval history and audit trail for an announcement.
    
    **History includes:**
    - All approval/rejection actions
    - Submitter and approver details
    - Timeline of all workflow events
    - Decision rationales and feedback
    - System-generated events
    
    **Audit compliance:**
    - Immutable historical records
    - Full actor attribution
    - Timestamp precision
    - Change reason tracking
    """,
    response_description="Complete approval audit trail"
)
@log_endpoint_call
async def get_approval_history(
    announcement_id: UUID,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> ApprovalHistory:
    """
    Get comprehensive approval history with full audit trail.
    """
    try:
        result = await service.get_history(
            announcement_id=str(announcement_id),
            actor_id=current_user.id,
        )
        
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History not found")
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"History retrieval failed: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="History retrieval failed")


# ---------------------------------------------------------------------------
# Request Management
# ---------------------------------------------------------------------------

@router.post(
    "/{approval_id}/withdraw",
    status_code=status.HTTP_200_OK,
    summary="Withdraw submitted approval request",
    description="""
    Withdraw a pending approval request before it's been processed.
    
    **Withdrawal conditions:**
    - Request must be in pending state
    - Only submitter or admin can withdraw
    - Cannot withdraw after approval/rejection
    
    **Effects:**
    - Removes from approval queues
    - Returns announcement to draft state
    - Notifies relevant approvers
    - Records withdrawal in audit trail
    """,
    responses={
        200: {"description": "Approval request withdrawn successfully"},
        409: {"description": "Cannot withdraw processed request"}
    }
)
@require_permissions(["announcement:withdraw_approval"])
@log_endpoint_call
async def withdraw_approval_submission(
    approval_id: UUID,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> dict[str, str]:
    """
    Withdraw pending approval request with state validation.
    """
    try:
        logger.info(
            f"Withdrawing approval request {approval_id}",
            extra={"actor_id": current_user.id, "approval_id": str(approval_id)}
        )
        
        await service.withdraw_submission(approval_id=str(approval_id), actor_id=current_user.id)
        
        logger.info(
            f"Successfully withdrew approval request {approval_id}",
            extra={"actor_id": current_user.id, "approval_id": str(approval_id)}
        )
        
        return {"detail": "Approval submission withdrawn successfully"}
        
    except ValueError as e:
        logger.warning(f"Invalid withdrawal: {str(e)}", extra={"approval_id": str(approval_id)})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for withdrawal", extra={"actor_id": current_user.id, "approval_id": str(approval_id)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    except Exception as e:
        logger.error(f"Withdrawal failed: {str(e)}", extra={"approval_id": str(approval_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Withdrawal failed")