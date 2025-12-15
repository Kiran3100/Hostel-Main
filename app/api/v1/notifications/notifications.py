# app/api/v1/notifications/notifications.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status, Response
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.notification import NotificationService
from app.schemas.notification.notification_base import (
    MarkAsRead,
    BulkMarkAsRead,
    NotificationDelete,
)
from app.schemas.notification.notification_response import (
    NotificationList,
    NotificationDetail,
    UnreadCount,
    NotificationSummary,
)
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Notifications - In-App"])


def _get_service(session: Session) -> NotificationService:
    uow = UnitOfWork(session)
    return NotificationService(uow)


@router.get("/", response_model=NotificationList)
def list_my_notifications(
    only_unread: bool = Query(
        False,
        description="If true, return only unread notifications",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Maximum number of notifications to return",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationList:
    """
    List notifications for the authenticated user.
    """
    service = _get_service(session)
    # Expected: list_notifications_for_user(user_id, only_unread, limit) -> NotificationList
    return service.list_notifications_for_user(
        user_id=current_user.id,
        only_unread=only_unread,
        limit=limit,
    )


@router.get("/unread-count", response_model=UnreadCount)
def get_unread_count(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> UnreadCount:
    """
    Get unread notifications count for the authenticated user.
    """
    service = _get_service(session)
    # Expected: get_unread_count_for_user(user_id) -> UnreadCount
    return service.get_unread_count_for_user(user_id=current_user.id)


@router.get("/summary", response_model=NotificationSummary)
def get_notification_summary(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationSummary:
    """
    Get notification summary (unread counts per type/category, etc.).
    """
    service = _get_service(session)
    # Expected: get_summary_for_user(user_id) -> NotificationSummary
    return service.get_summary_for_user(user_id=current_user.id)


@router.get("/{notification_id}", response_model=NotificationDetail)
def get_notification(
    notification_id: str,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationDetail:
    """
    Get details of a single notification.
    """
    service = _get_service(session)
    # Expected: get_notification_for_user(notification_id, user_id) -> NotificationDetail
    return service.get_notification_for_user(
        notification_id=notification_id,
        user_id=current_user.id,
    )


@router.post("/{notification_id}/read", response_model=NotificationDetail)
def mark_notification_as_read(
    notification_id: str,
    payload: MarkAsRead | None = None,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationDetail:
    """
    Mark a single notification as read.
    """
    service = _get_service(session)
    # Expected: mark_as_read(user_id, notification_id, data: Optional[MarkAsRead]) -> NotificationDetail
    return service.mark_as_read(
        user_id=current_user.id,
        notification_id=notification_id,
        data=payload,
    )


@router.post("/read/bulk", response_model=NotificationList)
def bulk_mark_as_read(
    payload: BulkMarkAsRead,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationList:
    """
    Bulk mark multiple notifications as read.
    """
    service = _get_service(session)
    # Expected: bulk_mark_as_read(user_id, data: BulkMarkAsRead) -> NotificationList
    return service.bulk_mark_as_read(
        user_id=current_user.id,
        data=payload,
    )


@router.delete("/{notification_id}")
def delete_notification(
    notification_id: str,
    reason: Optional[str] = Query(None, description="Deletion reason (optional)"),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """
    Delete (or soft-delete) a single notification.
    """
    service = _get_service(session)
    
    # Create NotificationDelete object from query parameter if needed
    delete_data = NotificationDelete(reason=reason) if reason else None
    
    # Expected: delete_notification(user_id, notification_id, data: Optional[NotificationDelete]) -> None
    service.delete_notification(
        user_id=current_user.id,
        notification_id=notification_id,
        data=delete_data,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)