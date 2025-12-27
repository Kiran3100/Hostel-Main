from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
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

router = APIRouter(prefix="/announcements/approval", tags=["announcements:approval"])


def get_approval_service(db: Session = Depends(deps.get_db)) -> AnnouncementApprovalService:
    return AnnouncementApprovalService(db=db)


@router.post(
    "/submit",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit announcement for approval",
)
def submit_for_approval(
    payload: ApprovalRequest,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> Any:
    return service.submit_for_approval(
        payload=payload,
        actor_id=current_user.id,
    )


@router.post(
    "/{approval_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve announcement",
)
def approve_announcement(
    approval_id: str,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> Any:
    return service.approve(
        approval_id=approval_id,
        actor_id=current_user.id,
    )


@router.post(
    "/{approval_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject announcement",
)
def reject_announcement(
    approval_id: str,
    payload: RejectionRequest,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> Any:
    return service.reject(
        approval_id=approval_id,
        payload=payload,
        actor_id=current_user.id,
    )


@router.post(
    "/bulk-decide",
    response_model=List[ApprovalResponse],
    summary="Bulk approve/reject announcements",
)
def bulk_decide(
    payload: BulkApproval,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> Any:
    return service.bulk_decide(
        payload=payload,
        actor_id=current_user.id,
    )


@router.get(
    "/workflows/{announcement_id}",
    response_model=ApprovalWorkflow,
    summary="Get approval workflow for announcement",
)
def get_approval_workflow(
    announcement_id: str,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> Any:
    return service.get_workflow(
        announcement_id=announcement_id,
        actor_id=current_user.id,
    )


@router.get(
    "/queue",
    response_model=SupervisorApprovalQueue,
    summary="Get supervisor's approval queue",
)
def get_supervisor_queue(
    current_user=Depends(deps.get_supervisor_user),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> Any:
    return service.get_supervisor_queue(supervisor_id=current_user.id)


@router.get(
    "/history/{announcement_id}",
    response_model=ApprovalHistory,
    summary="Get approval history for announcement",
)
def get_approval_history(
    announcement_id: str,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> Any:
    return service.get_history(
        announcement_id=announcement_id,
        actor_id=current_user.id,
    )


@router.post(
    "/{approval_id}/withdraw",
    status_code=status.HTTP_200_OK,
    summary="Withdraw submitted approval request",
)
def withdraw_approval_submission(
    approval_id: str,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementApprovalService = Depends(get_approval_service),
) -> Any:
    service.withdraw_submission(approval_id=approval_id, actor_id=current_user.id)
    return {"detail": "Approval submission withdrawn"}