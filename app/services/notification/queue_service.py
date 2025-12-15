# app/services/notification/queue_service.py
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Protocol
from uuid import UUID

from app.schemas.notification.notification_queue import (
    QueueStatus,
    QueuedNotification,
    BatchProcessing,
    QueueStats,
)
from app.schemas.common.enums import NotificationType, Priority
from app.schemas.common.filters import DateRangeFilter


class NotificationQueueStore(Protocol):
    """
    Storage abstraction for queued notifications and batch processing.
    """

    # Queue
    def enqueue(self, record: dict) -> None: ...
    def get(self, notification_id: UUID) -> Optional[dict]: ...
    def update(self, notification_id: UUID, data: dict) -> None: ...
    def list_all(self) -> List[dict]: ...

    # Batches (optional, not fully used here)
    def save_batch(self, record: dict) -> None: ...
    def get_batch(self, batch_id: UUID) -> Optional[dict]: ...
    def list_batches(self) -> List[dict]: ...


class QueueService:
    """
    Notification queue management:

    - Enqueue notifications for async processing
    - Update status (processing, completed, failed)
    - Provide high-level queue status & stats
    """

    def __init__(self, store: NotificationQueueStore) -> None:
        self._store = store

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Enqueue & update
    # ------------------------------------------------------------------ #
    def enqueue_notification(
        self,
        *,
        notification_id: UUID,
        notification_type: NotificationType,
        priority: Priority,
        recipient: str,
        scheduled_at: Optional[datetime] = None,
        max_retries: int = 3,
    ) -> QueuedNotification:
        now = self._now()
        record = {
            "notification_id": notification_id,
            "notification_type": notification_type,
            "priority": priority,
            "status": "queued",  # NotificationStatus as string
            "recipient": recipient,
            "scheduled_at": scheduled_at,
            "queued_at": now,
            "retry_count": 0,
            "max_retries": max_retries,
            "estimated_send_time": scheduled_at or now,
        }
        self._store.enqueue(record)
        return QueuedNotification.model_validate(record)

    def update_status(
        self,
        notification_id: UUID,
        *,
        status: str,
        retry_count: Optional[int] = None,
        estimated_send_time: Optional[datetime] = None,
    ) -> QueuedNotification:
        rec = self._store.get(notification_id)
        if not rec:
            raise ValueError(f"Queued notification {notification_id} not found")

        rec["status"] = status
        if retry_count is not None:
            rec["retry_count"] = retry_count
        if estimated_send_time is not None:
            rec["estimated_send_time"] = estimated_send_time

        self._store.update(notification_id, rec)
        return QueuedNotification.model_validate(rec)

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #
    def get_queue_status(self) -> QueueStatus:
        records = self._store.list_all()
        total_queued = sum(1 for r in records if r.get("status") == "queued")
        total_processing = sum(1 for r in records if r.get("status") == "processing")
        total_failed = sum(1 for r in records if r.get("status") == "failed")

        urgent_queued = sum(
            1
            for r in records
            if r.get("status") == "queued"
            and r.get("priority") == Priority.CRITICAL
        )
        high_queued = sum(
            1
            for r in records
            if r.get("status") == "queued"
            and r.get("priority") == Priority.HIGH
        )
        medium_queued = sum(
            1
            for r in records
            if r.get("status") == "queued"
            and r.get("priority") == Priority.MEDIUM
        )
        low_queued = sum(
            1
            for r in records
            if r.get("status") == "queued"
            and r.get("priority") == Priority.LOW
        )

        email_queued = sum(
            1
            for r in records
            if r.get("status") == "queued"
            and r.get("notification_type") == NotificationType.EMAIL
        )
        sms_queued = sum(
            1
            for r in records
            if r.get("status") == "queued"
            and r.get("notification_type") == NotificationType.SMS
        )
        push_queued = sum(
            1
            for r in records
            if r.get("status") == "queued"
            and r.get("notification_type") == NotificationType.PUSH
        )

        return QueueStatus(
            total_queued=total_queued,
            total_processing=total_processing,
            total_failed=total_failed,
            urgent_queued=urgent_queued,
            high_queued=high_queued,
            medium_queued=medium_queued,
            low_queued=low_queued,
            email_queued=email_queued,
            sms_queued=sms_queued,
            push_queued=push_queued,
            avg_processing_time_seconds=Decimal("0"),
            throughput_per_minute=Decimal("0"),
        )

    def get_queue_stats(self, period: DateRangeFilter) -> QueueStats:
        """
        Placeholder implementation.

        A real implementation would require per-notification timestamps
        (when queued, when processed, etc.). Here we return zeros.
        """
        start = period.start_date or date.min
        end = period.end_date or date.max

        return QueueStats(
            current_queue_size=len(self._store.list_all()),
            oldest_queued_age_minutes=None,
            today_processed=0,
            today_successful=0,
            today_failed=0,
            success_rate=Decimal("0"),
            failure_rate=Decimal("0"),
            average_queue_time_minutes=Decimal("0"),
            average_processing_time_seconds=Decimal("0"),
        )