# app/services/notification/notification_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol
from uuid import UUID, uuid4

from app.schemas.notification import (
    NotificationCreate,
    NotificationUpdate,
    NotificationResponse,
    NotificationList,
    UnreadCount,
    NotificationDetail,
)
from app.schemas.notification.notification_response import NotificationListItem
from app.schemas.notification.notification_base import (
    MarkAsRead,
    BulkMarkAsRead,
    NotificationDelete,
)
from app.schemas.common.enums import NotificationType, Priority
from app.services.common import errors
from app.services.notification.email_service import EmailService
from app.services.notification.sms_service import SMSService
from app.services.notification.push_service import PushService


class NotificationStore(Protocol):
    """
    Storage abstraction for in-app notifications.

    Expected record keys (example):
        {
            "id": UUID,
            "recipient_user_id": UUID | None,
            "recipient_email": str | None,
            "recipient_phone": str | None,
            "notification_type": NotificationType,
            "template_code": str | None,
            "subject": str | None,
            "message_body": str,
            "priority": Priority,
            "status": str,
            "scheduled_at": datetime | None,
            "sent_at": datetime | None,
            "failed_at": datetime | None,
            "failure_reason": str | None,
            "retry_count": int,
            "max_retries": int,
            "metadata": dict,
            "hostel_id": UUID | None,
            "is_read": bool,
            "read_at": datetime | None,
            "created_at": datetime,
            "updated_at": datetime,
        }
    """

    def save_notification(self, record: dict) -> dict: ...
    def update_notification(self, notification_id: UUID, data: dict) -> dict: ...
    def get_notification(self, notification_id: UUID) -> Optional[dict]: ...
    def list_notifications_for_user(self, user_id: UUID) -> List[dict]: ...
    def mark_read(self, notification_id: UUID, user_id: UUID) -> None: ...
    def mark_bulk_read(self, notification_ids: List[UUID], user_id: UUID) -> None: ...
    def delete_notification(self, notification_id: UUID, permanent: bool) -> None: ...


class NotificationService:
    """
    High-level notification orchestrator (in-app + channels):

    - Create & (optionally) dispatch notifications
    - Map to Email/SMS/Push services when sending immediately
    - Read/unread management and listing
    """

    def __init__(
        self,
        store: NotificationStore,
        email_service: Optional[EmailService] = None,
        sms_service: Optional[SMSService] = None,
        push_service: Optional[PushService] = None,
    ) -> None:
        self._store = store
        self._email_service = email_service
        self._sms_service = sms_service
        self._push_service = push_service

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_response(self, rec: dict) -> NotificationResponse:
        return NotificationResponse(
            id=rec["id"],
            created_at=rec["created_at"],
            updated_at=rec["updated_at"],
            recipient_user_id=rec.get("recipient_user_id"),
            recipient_email=rec.get("recipient_email"),
            recipient_phone=rec.get("recipient_phone"),
            notification_type=rec["notification_type"],
            subject=rec.get("subject"),
            message_body=rec["message_body"],
            priority=rec["priority"].value if hasattr(rec["priority"], "value") else str(rec["priority"]),
            status=rec["status"],
            scheduled_at=rec.get("scheduled_at"),
            sent_at=rec.get("sent_at"),
        )

    def _to_detail(self, rec: dict) -> NotificationDetail:
        return NotificationDetail(
            id=rec["id"],
            created_at=rec["created_at"],
            updated_at=rec["updated_at"],
            recipient_user_id=rec.get("recipient_user_id"),
            recipient_email=rec.get("recipient_email"),
            recipient_phone=rec.get("recipient_phone"),
            notification_type=rec["notification_type"],
            template_code=rec.get("template_code"),
            subject=rec.get("subject"),
            message_body=rec["message_body"],
            priority=rec["priority"].value if hasattr(rec["priority"], "value") else str(rec["priority"]),
            status=rec["status"],
            scheduled_at=rec.get("scheduled_at"),
            sent_at=rec.get("sent_at"),
            failed_at=rec.get("failed_at"),
            failure_reason=rec.get("failure_reason"),
            retry_count=rec.get("retry_count", 0),
            max_retries=rec.get("max_retries", 0),
            metadata=rec.get("metadata", {}),
            hostel_id=rec.get("hostel_id"),
            # timestamps already set
        )

    def _to_list_item(self, rec: dict) -> NotificationListItem:
        body = rec["message_body"] or ""
        preview = body[:100]
        return NotificationListItem(
            id=rec["id"],
            notification_type=rec["notification_type"],
            subject=rec.get("subject"),
            message_preview=preview,
            priority=rec["priority"].value if hasattr(rec["priority"], "value") else str(rec["priority"]),
            is_read=rec.get("is_read", False),
            read_at=rec.get("read_at"),
            created_at=rec["created_at"],
            action_url=rec.get("metadata", {}).get("action_url"),
            icon=rec.get("metadata", {}).get("icon"),
        )

    # ------------------------------------------------------------------ #
    # Core create / send
    # ------------------------------------------------------------------ #
    def create_notification(
        self,
        data: NotificationCreate,
        *,
        send_immediately: bool = True,
        max_retries: int = 3,
    ) -> NotificationDetail:
        """
        Create an in-app notification and optionally dispatch to its channel.

        For scheduled notifications (scheduled_at != None), send_immediately
        should typically be False and a queue/worker should handle dispatch.
        """
        now = self._now()
        nid = uuid4()

        priority: Priority = getattr(data, "priority", None) or Priority.MEDIUM

        record = {
            "id": nid,
            "recipient_user_id": data.recipient_user_id,
            "recipient_email": data.recipient_email,
            "recipient_phone": data.recipient_phone,
            "notification_type": data.notification_type,
            "template_code": data.template_code,
            "subject": data.subject,
            "message_body": data.message_body,
            "priority": priority,
            "status": "queued",  # string; NotificationStatus handled by schema
            "scheduled_at": data.scheduled_at,
            "sent_at": None,
            "failed_at": None,
            "failure_reason": None,
            "retry_count": 0,
            "max_retries": max_retries,
            "metadata": data.metadata or {},
            "hostel_id": data.hostel_id,
            "is_read": False,
            "read_at": None,
            "created_at": now,
            "updated_at": now,
        }
        saved = self._store.save_notification(record)

        # Synchronous send if requested and not scheduled in the future
        if send_immediately and not data.scheduled_at:
            self._dispatch_channel(saved)

        fresh = self._store.get_notification(nid) or saved
        return self._to_detail(fresh)

    def _dispatch_channel(self, rec: dict) -> None:
        """
        Dispatch notification to the underlying channel service.
        """
        ntype: NotificationType = rec["notification_type"]
        now = self._now()

        try:
            if ntype == NotificationType.EMAIL and self._email_service:
                from app.schemas.notification.email_notification import EmailRequest

                if not rec.get("recipient_email"):
                    raise errors.ValidationError("recipient_email required for email notification")

                email_req = EmailRequest(
                    recipient_email=rec["recipient_email"],
                    cc_emails=[],
                    bcc_emails=[],
                    subject=rec.get("subject") or "",
                    body_html=rec["message_body"],
                    body_text=None,
                    attachments=[],
                    template_code=rec.get("template_code"),
                    template_variables=None,
                    reply_to=None,
                    from_name=None,
                    track_opens=True,
                    track_clicks=True,
                    priority="normal",
                )
                self._email_service.send_email(email_req)

            elif ntype == NotificationType.SMS and self._sms_service:
                from app.schemas.notification.sms_notification import SMSRequest

                if not rec.get("recipient_phone"):
                    raise errors.ValidationError("recipient_phone required for SMS notification")

                sms_req = SMSRequest(
                    recipient_phone=rec["recipient_phone"],
                    message=rec["message_body"],
                    template_code=rec.get("template_code"),
                    template_variables=None,
                    sender_id=None,
                    priority="normal",
                    dlt_template_id=None,
                )
                self._sms_service.send_sms(sms_req)

            elif ntype == NotificationType.PUSH and self._push_service:
                from app.schemas.notification.push_notification import PushRequest

                if not rec.get("recipient_user_id"):
                    raise errors.ValidationError("recipient_user_id required for push notification")

                push_req = PushRequest(
                    user_id=rec["recipient_user_id"],
                    device_token=None,
                    device_tokens=None,
                    title=rec.get("subject") or "",
                    body=rec["message_body"],
                    data=rec.get("metadata", {}),
                    action_url=rec.get("metadata", {}).get("action_url"),
                    icon=None,
                    image_url=None,
                    badge_count=None,
                    sound="default",
                    priority="normal",
                    ttl=86400,
                )
                self._push_service.send_push(push_req)

            # If we reach here without error, treat as sent
            rec["status"] = "sent"
            rec["sent_at"] = now
            rec["updated_at"] = now
            self._store.update_notification(rec["id"], rec)

        except errors.ServiceError as exc:
            rec["status"] = "failed"
            rec["failed_at"] = now
            rec["failure_reason"] = str(exc)
            rec["updated_at"] = now
            self._store.update_notification(rec["id"], rec)
        except Exception as exc:  # pragma: no cover
            rec["status"] = "failed"
            rec["failed_at"] = now
            rec["failure_reason"] = str(exc)
            rec["updated_at"] = now
            self._store.update_notification(rec["id"], rec)

    # ------------------------------------------------------------------ #
    # Read ops
    # ------------------------------------------------------------------ #
    def get_notification(self, notification_id: UUID) -> NotificationDetail:
        rec = self._store.get_notification(notification_id)
        if not rec:
            raise errors.NotFoundError(f"Notification {notification_id} not found")
        return self._to_detail(rec)

    def list_notifications_for_user(self, user_id: UUID) -> NotificationList:
        recs = self._store.list_notifications_for_user(user_id)
        items = [
            self._to_list_item(r)
            for r in sorted(recs, key=lambda x: x["created_at"], reverse=True)
        ]
        total = len(items)
        unread = sum(1 for r in recs if not r.get("is_read"))
        return NotificationList(
            user_id=user_id,
            total_notifications=total,
            unread_count=unread,
            notifications=items,
        )

    def get_unread_count(self, user_id: UUID) -> UnreadCount:
        recs = self._store.list_notifications_for_user(user_id)
        total_unread = sum(1 for r in recs if not r.get("is_read"))

        email_unread = sum(
            1 for r in recs if not r.get("is_read") and r["notification_type"] == NotificationType.EMAIL
        )
        sms_unread = sum(
            1 for r in recs if not r.get("is_read") and r["notification_type"] == NotificationType.SMS
        )
        push_unread = sum(
            1 for r in recs if not r.get("is_read") and r["notification_type"] == NotificationType.PUSH
        )
        in_app_unread = total_unread  # union here

        urgent_unread = sum(
            1
            for r in recs
            if not r.get("is_read") and r.get("priority") == Priority.CRITICAL
        )
        high_unread = sum(
            1
            for r in recs
            if not r.get("is_read") and r.get("priority") == Priority.HIGH
        )

        return UnreadCount(
            user_id=user_id,
            total_unread=total_unread,
            email_unread=email_unread,
            sms_unread=sms_unread,
            push_unread=push_unread,
            in_app_unread=in_app_unread,
            urgent_unread=urgent_unread,
            high_unread=high_unread,
        )

    # ------------------------------------------------------------------ #
    # Read/mark/delete
    # ------------------------------------------------------------------ #
    def mark_as_read(self, data: MarkAsRead) -> None:
        self._store.mark_read(data.notification_id, data.user_id)

    def bulk_mark_as_read(self, data: BulkMarkAsRead) -> None:
        self._store.mark_bulk_read(data.notification_ids, data.user_id)

    def delete_notification(self, data: NotificationDelete) -> None:
        self._store.delete_notification(data.notification_id, data.permanent)