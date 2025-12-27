from typing import Any, List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.leave.leave_approval import (
    LeaveApprovalRequest,
    LeaveApprovalAction,
    LeaveApprovalResponse,
)
from app.services.leave.leave_approval_service import LeaveApprovalService

router = APIRouter(prefix="/leaves/approval", tags=["leaves:approval"])


def get_approval_service(db: Session = Depends(deps.get_db)) -> LeaveApprovalService:
    return LeaveApprovalService(db=db)


@router.post(
    "/{leave_id}/decide",
    response_model=LeaveApprovalResponse,
    summary="Approve/Reject leave application",
)
def decide_leave(
    leave_id: str,
    payload: LeaveApprovalRequest,
    current_user=Depends(deps.get_current_user),
    service: LeaveApprovalService = Depends(get_approval_service),
) -> Any:
    """
    Simple approval decision (Approve/Reject).
    """
    return service.decide(leave_id, payload, approver_id=current_user.id)


@router.post(
    "/{leave_id}/workflow",
    summary="Execute workflow action (escalate/delegate)",
)
def workflow_action(
    leave_id: str,
    payload: LeaveApprovalAction,
    current_user=Depends(deps.get_current_user),
    service: LeaveApprovalService = Depends(get_approval_service),
) -> Any:
    return service.workflow_action(
        leave_id, payload, actor_id=current_user.id
    )


@router.get(
    "/pending",
    response_model=List[Any],  # Replace with LeaveListItem or similar
    summary="Get pending approvals for current user",
)
def get_pending_approvals(
    current_user=Depends(deps.get_current_user),
    service: LeaveApprovalService = Depends(get_approval_service),
) -> Any:
    return service.get_pending_approvals(approver_id=current_user.id)


@router.get(
    "/{leave_id}/history",
    summary="Get approval history",
)
def get_approval_history(
    leave_id: str,
    current_user=Depends(deps.get_current_user),
    service: LeaveApprovalService = Depends(get_approval_service),
) -> Any:
    return service.get_history(leave_id)