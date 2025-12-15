# app/api/v1/notifications/send.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.notification import (
    NotificationService,
    EmailService,
    SMSService,
    PushService,
)
from app.schemas.notification.notification_base import NotificationCreate
from app.schemas.notification.notification_response import NotificationDetail
from app.schemas.notification.email_notification import (
    EmailRequest,
    BulkEmailRequest,
    EmailStats,
)
from app.schemas.notification.sms_notification import (
    SMSRequest,
    BulkSMSRequest,
    SMSStats,
)
from app.schemas.notification.push_notification import (
    PushRequest,
    PushStats,
)
from . import CurrentUser, get_current_user, get_current_admin

router = APIRouter(tags=["Notifications - Send"])


def _get_notification_service(session: Session) -> NotificationService:
    uow = UnitOfWork(session)
    return NotificationService(uow)


def _get_email_service(session: Session) -> EmailService:
    uow = UnitOfWork(session)
    return EmailService(uow)


def _get_sms_service(session: Session) -> SMSService:
    uow = UnitOfWork(session)
    return SMSService(uow)


def _get_push_service(session: Session) -> PushService:
    uow = UnitOfWork(session)
    return PushService(uow)


# In-app notifications --------------------------------------------------------


@router.post("/in-app", response_model=NotificationDetail, status_code=status.HTTP_201_CREATED)
def send_in_app_notification(
    payload: NotificationCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> NotificationDetail:
    """
    Create and dispatch an in-app notification (admin-triggered).
    """
    service = _get_notification_service(session)
    # Expected: send_notification(created_by: UUID, data: NotificationCreate) -> NotificationDetail
    return service.send_notification(
        created_by=current_user.id,
        data=payload,
    )


# Email -----------------------------------------------------------------------


@router.post("/email", response_model=EmailStats)
def send_email(
    payload: EmailRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> EmailStats:
    """
    Send a single email via EmailService.
    """
    service = _get_email_service(session)
    # Expected: send_email(requester_id: UUID, data: EmailRequest) -> EmailStats | similar
    return service.send_email(
        requester_id=current_user.id,
        data=payload,
    )


@router.post("/email/bulk", response_model=EmailStats)
def send_bulk_email(
    payload: BulkEmailRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> EmailStats:
    """
    Send bulk emails via EmailService.
    """
    service = _get_email_service(session)
    # Expected: send_bulk_email(requester_id: UUID, data: BulkEmailRequest) -> EmailStats
    return service.send_bulk_email(
        requester_id=current_user.id,
        data=payload,
    )


@router.get("/email/stats", response_model=EmailStats)
def get_email_stats(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> EmailStats:
    """
    Get high-level email stats.
    """
    service = _get_email_service(session)
    # Expected: get_stats() -> EmailStats
    return service.get_stats()


# SMS -------------------------------------------------------------------------


@router.post("/sms", response_model=SMSStats)
def send_sms(
    payload: SMSRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> SMSStats:
    """
    Send a single SMS via SMSService.
    """
    service = _get_sms_service(session)
    # Expected: send_sms(requester_id: UUID, data: SMSRequest) -> SMSStats
    return service.send_sms(
        requester_id=current_user.id,
        data=payload,
    )


@router.post("/sms/bulk", response_model=SMSStats)
def send_bulk_sms(
    payload: BulkSMSRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> SMSStats:
    """
    Send bulk SMS via SMSService.
    """
    service = _get_sms_service(session)
    # Expected: send_bulk_sms(requester_id: UUID, data: BulkSMSRequest) -> SMSStats
    return service.send_bulk_sms(
        requester_id=current_user.id,
        data=payload,
    )


@router.get("/sms/stats", response_model=SMSStats)
def get_sms_stats(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> SMSStats:
    """
    Get high-level SMS stats.
    """
    service = _get_sms_service(session)
    # Expected: get_stats() -> SMSStats
    return service.get_stats()


# Push ------------------------------------------------------------------------


@router.post("/push", response_model=PushStats)
def send_push(
    payload: PushRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> PushStats:
    """
    Send a push notification via PushService.
    """
    service = _get_push_service(session)
    # Expected: send_push(requester_id: UUID, data: PushRequest) -> PushStats
    return service.send_push(
        requester_id=current_user.id,
        data=payload,
    )


@router.get("/push/stats", response_model=PushStats)
def get_push_stats(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> PushStats:
    """
    Get high-level push notification stats.
    """
    service = _get_push_service(session)
    # Expected: get_stats() -> PushStats
    return service.get_stats()