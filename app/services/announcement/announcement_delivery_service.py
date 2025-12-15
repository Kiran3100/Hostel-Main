# app/services/announcement/announcement_delivery_service.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Dict, Optional, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import AnnouncementRepository
from app.schemas.announcement.announcement_delivery import (
    DeliveryConfig,
    DeliveryChannels,
    DeliveryStatus,
    DeliveryReport,
    ChannelDeliveryStats,
    FailedDelivery,
)
from app.services.common import UnitOfWork, errors


class AnnouncementDeliveryStore(Protocol):
    """
    Abstract storage for announcement delivery configuration and status.

    Implementations can use Redis, dedicated tables, etc.
    """

    # Config
    def get_config(self, announcement_id: UUID) -> Optional[dict]: ...
    def save_config(self, announcement_id: UUID, data: dict) -> None: ...

    # Status
    def get_status(self, announcement_id: UUID) -> Optional[dict]: ...
    def save_status(self, announcement_id: UUID, data: dict) -> None: ...

    # Failed recipients
    def list_failed_recipients(self, announcement_id: UUID) -> list[dict]: ...
    def add_failed_recipient(self, announcement_id: UUID, record: dict) -> None: ...

    # Cached reports
    def get_report(self, announcement_id: UUID) -> Optional[dict]: ...
    def save_report(self, announcement_id: UUID, data: dict) -> None: ...


class AnnouncementDeliveryService:
    """
    Delivery configuration & aggregate status for announcements.

    - Store/load DeliveryConfig
    - Track DeliveryStatus per announcement
    - Record failed recipients (for later retry)
    - Build DeliveryReport
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: AnnouncementDeliveryStore,
    ) -> None:
        self._session_factory = session_factory
        self._store = store

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_announcement_repo(self, uow: UnitOfWork) -> AnnouncementRepository:
        return uow.get_repo(AnnouncementRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def set_delivery_config(self, config: DeliveryConfig) -> DeliveryConfig:
        """
        Persist delivery configuration for an announcement.
        """
        self._store.save_config(config.announcement_id, config.model_dump())
        return config

    def get_delivery_config(self, announcement_id: UUID) -> Optional[DeliveryConfig]:
        record = self._store.get_config(announcement_id)
        if not record:
            return None
        return DeliveryConfig.model_validate(record)

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #
    def initialize_status(
        self,
        announcement_id: UUID,
        *,
        total_recipients: int,
    ) -> DeliveryStatus:
        """
        Initialize DeliveryStatus with zero counts for all channels.

        Typically called before starting delivery.
        """
        status = DeliveryStatus(
            announcement_id=announcement_id,
            total_recipients=total_recipients,
            email_sent=0,
            email_delivered=0,
            email_failed=0,
            sms_sent=0,
            sms_delivered=0,
            sms_failed=0,
            push_sent=0,
            push_delivered=0,
            push_failed=0,
            total_delivered=0,
            total_failed=0,
            delivery_rate=Decimal("0"),
            delivery_started_at=None,
            delivery_completed_at=None,
        )
        self._store.save_status(announcement_id, status.model_dump())
        return status

    def get_delivery_status(self, announcement_id: UUID) -> Optional[DeliveryStatus]:
        record = self._store.get_status(announcement_id)
        if not record:
            return None
        return DeliveryStatus.model_validate(record)

    def mark_delivery_started(self, announcement_id: UUID) -> DeliveryStatus:
        status = self.get_delivery_status(announcement_id)
        if not status:
            raise errors.NotFoundError(
                f"DeliveryStatus for announcement {announcement_id} not initialized"
            )
        status.delivery_started_at = self._now()
        self._store.save_status(announcement_id, status.model_dump())
        return status

    def mark_delivery_completed(self, announcement_id: UUID) -> DeliveryStatus:
        status = self.get_delivery_status(announcement_id)
        if not status:
            raise errors.NotFoundError(
                f"DeliveryStatus for announcement {announcement_id} not initialized"
            )
        status.delivery_completed_at = self._now()
        self._store.save_status(announcement_id, status.model_dump())
        return status

    def record_channel_outcome(
        self,
        announcement_id: UUID,
        *,
        channel: str,
        sent: int = 0,
        delivered: int = 0,
        failed: int = 0,
    ) -> DeliveryStatus:
        """
        Increment per-channel counters and recompute overall totals.

        channel: 'email' | 'sms' | 'push'
        """
        status = self.get_delivery_status(announcement_id)
        if not status:
            raise errors.NotFoundError(
                f"DeliveryStatus for announcement {announcement_id} not initialized"
            )

        if channel == "email":
            status.email_sent += sent
            status.email_delivered += delivered
            status.email_failed += failed
        elif channel == "sms":
            status.sms_sent += sent
            status.sms_delivered += delivered
            status.sms_failed += failed
        elif channel == "push":
            status.push_sent += sent
            status.push_delivered += delivered
            status.push_failed += failed
        else:
            # Unknown channel; ignore
            return status

        status.total_delivered = (
            status.email_delivered + status.sms_delivered + status.push_delivered
        )
        status.total_failed = (
            status.email_failed + status.sms_failed + status.push_failed
        )

        if status.total_recipients > 0:
            status.delivery_rate = (
                Decimal(str(status.total_delivered))
                / Decimal(str(status.total_recipients))
                * 100
            )
        else:
            status.delivery_rate = Decimal("0")

        self._store.save_status(announcement_id, status.model_dump())
        return status

    def record_failed_recipient(self, announcement_id: UUID, failed: FailedDelivery) -> None:
        """
        Track a single failed recipient (for retry or analysis).
        """
        self._store.add_failed_recipient(
            announcement_id,
            failed.model_dump(),
        )

    # ------------------------------------------------------------------ #
    # Report
    # ------------------------------------------------------------------ #
    def build_delivery_report(self, announcement_id: UUID) -> DeliveryReport:
        """
        Build a DeliveryReport from DeliveryStatus and failed recipients.
        """
        status = self.get_delivery_status(announcement_id)
        if not status:
            raise errors.NotFoundError(
                f"DeliveryStatus for announcement {announcement_id} not found"
            )

        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_announcement_repo(uow)
            a = repo.get(announcement_id)
            if a is None:
                raise errors.NotFoundError(f"Announcement {announcement_id} not found")
            title = a.title or ""

        duration_minutes: Optional[int] = None
        if status.delivery_started_at and status.delivery_completed_at:
            delta = status.delivery_completed_at - status.delivery_started_at
            duration_minutes = int(delta.total_seconds() // 60)

        # Per-channel stats
        def _channel_stats(
            channel: str, sent: int, delivered: int, failed: int
        ) -> ChannelDeliveryStats:
            pending = max(0, status.total_recipients - (delivered + failed))
            rate = (
                Decimal(str(delivered)) / Decimal(str(status.total_recipients)) * 100
                if status.total_recipients > 0
                else Decimal("0")
            )
            return ChannelDeliveryStats(
                channel=channel,
                sent=sent,
                delivered=delivered,
                failed=failed,
                pending=pending,
                delivery_rate=rate,
                average_delivery_time_seconds=None,
            )

        channel_breakdown: Dict[str, ChannelDeliveryStats] = {
            "email": _channel_stats(
                "email",
                status.email_sent,
                status.email_delivered,
                status.email_failed,
            ),
            "sms": _channel_stats(
                "sms",
                status.sms_sent,
                status.sms_delivered,
                status.sms_failed,
            ),
            "push": _channel_stats(
                "push",
                status.push_sent,
                status.push_delivered,
                status.push_failed,
            ),
        }

        failed_recs_raw = self._store.list_failed_recipients(announcement_id)
        failed_recipients: List[FailedDelivery] = [
            FailedDelivery.model_validate(r) for r in failed_recs_raw
        ]

        report = DeliveryReport(
            announcement_id=announcement_id,
            title=title,
            total_recipients=status.total_recipients,
            channel_breakdown=channel_breakdown,
            delivered_count=status.total_delivered,
            failed_count=status.total_failed,
            pending_count=max(
                0,
                status.total_recipients
                - (status.total_delivered + status.total_failed),
            ),
            failed_recipients=failed_recipients,
            delivery_duration_minutes=duration_minutes,
            generated_at=self._now(),
        )

        self._store.save_report(announcement_id, report.model_dump())
        return report

    def get_delivery_report(self, announcement_id: UUID) -> Optional[DeliveryReport]:
        record = self._store.get_report(announcement_id)
        if not record:
            return None
        return DeliveryReport.model_validate(record)