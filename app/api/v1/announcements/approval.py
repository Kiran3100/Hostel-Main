# api/v1/announcements/approval.py

from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.announcement.announcement_approval import (
    ApprovalRequest,
    ApprovalResponse,
    RejectionRequest,
    ApprovalWorkflow,
    SupervisorApprovalQueue,
    BulkApproval,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.announcement import AnnouncementService

router = APIRouter()


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{announcement_id}/approval/request",
    response_model=ApprovalWorkflow,
    status_code=status.HTTP_200_OK,
    summary="Request approval for an announcement",
)
async def request_approval(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: ApprovalRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalWorkflow:
    """
    Mark an announcement as requiring approval and create/update its approval workflow.
    """
    service = AnnouncementService(uow)
    try:
        return service.request_approval(
            announcement_id=announcement_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{announcement_id}/approval/approve",
    response_model=ApprovalResponse,
    summary="Approve an announcement",
)
async def approve_announcement(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: ApprovalRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalResponse:
    """
    Approve an announcement (typically by a supervisor/admin).
    """
    service = AnnouncementService(uow)
    try:
        return service.approve_announcement(
            announcement_id=announcement_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{announcement_id}/approval/reject",
    response_model=ApprovalResponse,
    summary="Reject an announcement",
)
async def reject_announcement(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: RejectionRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalResponse:
    """
    Reject an announcement with a structured rejection reason and notes.
    """
    service = AnnouncementService(uow)
    try:
        return service.reject_announcement(
            announcement_id=announcement_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/approvals/pending",
    response_model=SupervisorApprovalQueue,
    summary="List pending announcement approvals",
)
async def list_pending_approvals(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Optional hostel filter",
    ),
    approver_id: Union[UUID, None] = Query(
        None,
        description="Optional approver/supervisor filter",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> SupervisorApprovalQueue:
    """
    List pending announcement approvals, typically grouped by approver/supervisor.
    """
    service = AnnouncementService(uow)
    try:
        return service.list_pending_approvals(
            hostel_id=hostel_id,
            approver_id=approver_id,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/approvals/bulk",
    response_model=List[ApprovalResponse],
    summary="Bulk approve/reject announcements",
)
async def bulk_approve_announcements(
    payload: BulkApproval,
    uow: UnitOfWork = Depends(get_uow),
) -> List[ApprovalResponse]:
    """
    Bulk approval/rejection of multiple announcements in one call.
    """
    service = AnnouncementService(uow)
    try:
        return service.bulk_approve(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)